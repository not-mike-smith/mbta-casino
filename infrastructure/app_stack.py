from aws_cdk import CfnOutput, Duration, Fn, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticache as elasticache
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class AppStack(Stack):
    """
    Everything the application needs to run: network, database, cache,
    container services, and load balancer.

    Depends on DeploymentBootstrapStack for the ECR repository.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        repository: ecr.Repository,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -----------------------------------------------------------------------
        # Network
        # -----------------------------------------------------------------------

        # ECS runs in public subnets with public IPs — no NAT Gateway needed.
        # Security groups still control all inbound access; this is safe for a demo app.
        # RDS and Redis stay in private subnets (intra-VPC routing reaches them fine).
        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=0)

        # ECS tasks security group — ingress from ALB added after ALB is created
        ecs_sg = ec2.SecurityGroup(self, "EcsSg", vpc=vpc, description="ECS tasks")

        # RDS: accept connections from ECS tasks only
        rds_sg = ec2.SecurityGroup(self, "RdsSg", vpc=vpc, description="RDS")
        rds_sg.add_ingress_rule(ecs_sg, ec2.Port.tcp(5432), "From ECS")

        # Redis: accept connections from ECS tasks only
        redis_sg = ec2.SecurityGroup(self, "RedisSg", vpc=vpc, description="Redis")
        redis_sg.add_ingress_rule(ecs_sg, ec2.Port.tcp(6379), "From ECS")

        # -----------------------------------------------------------------------
        # Database (RDS PostgreSQL)
        # -----------------------------------------------------------------------

        db_instance = rds.DatabaseInstance(
            self,
            "Database",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_17
            ),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[rds_sg],
            database_name="mbta_casino",
            # CDK generates a random password and stores it in Secrets Manager
            # as a JSON object: { username, password, host, port, dbname, engine }
            credentials=rds.Credentials.from_generated_secret("mbta_casino"),
            removal_policy=RemovalPolicy.SNAPSHOT,
            deletion_protection=False,
        )

        assert db_instance.secret is not None, "RDS secret was not created"

        # -----------------------------------------------------------------------
        # Cache (ElastiCache Redis)
        # -----------------------------------------------------------------------

        private_subnet_ids = vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
        ).subnet_ids

        redis_subnet_group = elasticache.CfnSubnetGroup(
            self,
            "RedisSubnetGroup",
            description="mbta-casino Redis",
            subnet_ids=private_subnet_ids,
        )

        redis_cluster = elasticache.CfnCacheCluster(
            self,
            "RedisCluster",
            cache_node_type="cache.t3.micro",
            engine="redis",
            num_cache_nodes=1,
            cache_subnet_group_name=redis_subnet_group.ref,
            vpc_security_group_ids=[redis_sg.security_group_id],
        )

        # Redis has no credentials; the URL is not sensitive
        redis_url = Fn.join(
            "",
            [
                "redis://",
                redis_cluster.attr_redis_endpoint_address,
                ":",
                redis_cluster.attr_redis_endpoint_port,
                "/0",
            ],
        )

        # -----------------------------------------------------------------------
        # Secrets Manager
        # -----------------------------------------------------------------------

        django_secret_key = secretsmanager.Secret(
            self,
            "DjangoSecretKey",
            secret_name="mbta-casino/django-secret-key",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True,
                password_length=50,
            ),
        )

        # Placeholder — populate after deployment:
        # aws secretsmanager put-secret-value \
        #   --secret-id mbta-casino/mbta-api-key \
        #   --secret-string "YOUR_MBTA_API_KEY"
        mbta_api_key = secretsmanager.Secret(
            self,
            "MbtaApiKey",
            secret_name="mbta-casino/mbta-api-key",
        )

        # -----------------------------------------------------------------------
        # ECS
        # -----------------------------------------------------------------------

        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        api_log_group = logs.LogGroup(
            self,
            "ApiLogGroup",
            log_group_name="/ecs/mbta-casino/api",
            removal_policy=RemovalPolicy.DESTROY,
        )
        celery_log_group = logs.LogGroup(
            self,
            "CeleryLogGroup",
            log_group_name="/ecs/mbta-casino/celery",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ALB manages its own security group internally; we add rules via connections
        alb = elbv2.ApplicationLoadBalancer(self, "Alb", vpc=vpc, internet_facing=True)
        alb.connections.allow_from_any_ipv4(ec2.Port.tcp(80), "HTTP from internet")
        # Allow ALB to reach ECS tasks on port 8000
        ecs_sg.connections.allow_from(alb, ec2.Port.tcp(8000), "From ALB")

        # Environment variables shared by both the API and Celery containers.
        # DB host/port/name are not sensitive; credentials come from Secrets Manager.
        shared_environment = {
            "DJANGO_DEBUG": "false",
            "DB_HOST": db_instance.db_instance_endpoint_address,
            "DB_PORT": db_instance.db_instance_endpoint_port,
            "DB_NAME": "mbta_casino",
            "REDIS_URL": redis_url,
        }

        # Secrets injected as environment variables at container start.
        # CDK automatically grants the task execution role read access to each secret.
        shared_secrets = {
            "DJANGO_SECRET_KEY": ecs.Secret.from_secrets_manager(django_secret_key),  # type: ignore[arg-type]
            "MBTA_API_KEY": ecs.Secret.from_secrets_manager(mbta_api_key),  # type: ignore[arg-type]
            "DB_USER": ecs.Secret.from_secrets_manager(db_instance.secret, "username"),
            "DB_PASSWORD": ecs.Secret.from_secrets_manager(db_instance.secret, "password"),
        }

        # API task: runs entrypoint.sh (migrate + gunicorn)
        api_task_def = ecs.FargateTaskDefinition(self, "ApiTaskDef", memory_limit_mib=512, cpu=256)
        api_container = api_task_def.add_container(
            "api",
            image=ecs.ContainerImage.from_ecr_repository(repository, tag="latest"),
            environment={
                **shared_environment,
                # * is safe here: ECS tasks are in private subnets, only reachable via the ALB.
                # The ALB health checker hits the container IP directly, so we can't enumerate hosts.
                "DJANGO_ALLOWED_HOSTS": "*",
            },
            secrets=shared_secrets,
            logging=ecs.LogDriver.aws_logs(log_group=api_log_group, stream_prefix="api"),
        )
        api_container.add_port_mappings(ecs.PortMapping(container_port=8000))

        # Celery task: overrides the Dockerfile entrypoint to run the worker directly
        celery_task_def = ecs.FargateTaskDefinition(self, "CeleryTaskDef", memory_limit_mib=512, cpu=256)
        celery_task_def.add_container(
            "celery",
            image=ecs.ContainerImage.from_ecr_repository(repository, tag="latest"),
            entry_point=["celery"],
            command=["-A", "mbta_casino", "worker", "--beat", "-l", "info"],
            environment=shared_environment,
            secrets=shared_secrets,
            logging=ecs.LogDriver.aws_logs(log_group=celery_log_group, stream_prefix="celery"),
        )

        # -----------------------------------------------------------------------
        # ECS Services
        # -----------------------------------------------------------------------

        # assign_public_ip=True lets tasks reach ECR and the MBTA API without a NAT Gateway.
        ecs_subnets = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)

        api_service = ecs.FargateService(
            self,
            "ApiService",
            cluster=cluster,
            task_definition=api_task_def,
            desired_count=1,
            security_groups=[ecs_sg],
            assign_public_ip=True,
            vpc_subnets=ecs_subnets,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        )

        ecs.FargateService(
            self,
            "CeleryService",
            cluster=cluster,
            task_definition=celery_task_def,
            desired_count=1,
            security_groups=[ecs_sg],
            assign_public_ip=True,
            vpc_subnets=ecs_subnets,
        )

        # -----------------------------------------------------------------------
        # ALB → API
        # -----------------------------------------------------------------------

        listener = alb.add_listener("HttpListener", port=80)
        listener.add_targets(
            "ApiTargets",
            port=8000,
            targets=[api_service],
            health_check=elbv2.HealthCheck(
                path="/health_check",
                healthy_http_codes="200",
                interval=Duration.seconds(10),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=2,
            ),
        )

        # -----------------------------------------------------------------------
        # Outputs
        # -----------------------------------------------------------------------

        CfnOutput(self, "AlbDnsName", value=alb.load_balancer_dns_name)
        CfnOutput(
            self,
            "MbtaApiKeyInstruction",
            value=(
                "Run after deployment to set your MBTA API key: "
                "aws secretsmanager put-secret-value "
                "--secret-id mbta-casino/mbta-api-key "
                "--secret-string YOUR_KEY"
            ),
        )
