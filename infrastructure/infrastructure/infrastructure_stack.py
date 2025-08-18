from aws_cdk import (
    Stack,
    aws_logs as logs,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_elasticloadbalancingv2 as elbv2,
    CfnOutput,
    RemovalPolicy,
    Duration,
)
from constructs import Construct


class InfrastructureStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ECR
        repository = ecr.Repository(
            self,
            "MbtaApiRepo",
            repository_name="mbta_api",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # VPC
        vpc = ec2.Vpc(self, "MbtaApiVpc", max_azs=2)

        # Log Group
        log_group = logs.LogGroup(
            self,
            "MbtaApiEcsTaskLogGroup",
            log_group_name="/aws/ecs/mbta_api",
            removal_policy=RemovalPolicy.DESTROY,  # For dev
        )

        # ECS Cluster
        cluster = ecs.Cluster(
            self, "MbtaApiCluster", vpc=vpc, cluster_name="MbtaApiCluster"
        )

        # Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "MbtaApiTaskDef",
            family="MbtaApiTaskDef",
            memory_limit_mib=512,
            cpu=256
        )

        container = task_definition.add_container(
            "mbta-api-container",
            image=ecs.ContainerImage.from_ecr_repository(repository, tag="latest"),
            port_mappings=[ecs.PortMapping(container_port=8000)],
            environment={"ALLOWED_HOSTS": "*"},
            logging=ecs.LogDriver.aws_logs(
                log_group=log_group, stream_prefix="mbta_api"
            ),
        )

        # Application Load Balancer
        alb = elbv2.ApplicationLoadBalancer(
            self,
            "MbtaApiAlb",
            load_balancer_name="MbtaApiAlb",
            vpc=vpc,
            internet_facing=True,
        )

        # ECS Service
        service = ecs.FargateService(
            self,
            "MbtaApiService",
            service_name="MbtaApiService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
        )

        # Connect ALB to ECS
        listener = alb.add_listener("MbtaApiListener", port=80)  # HTTP only for now
        listener.add_targets(
            "MbtaApiTargets",
            target_group_name="MbtaApiTargetGroup",
            port=8000,
            targets=[service],
            health_check=elbv2.HealthCheck(
                enabled=True,
                healthy_http_codes="200",
                path="/health_check",  # Custom health check path
                protocol=elbv2.Protocol.HTTP,
                timeout=Duration.seconds(5),
                interval=Duration.seconds(30),
                healthy_threshold_count=2,
                unhealthy_threshold_count=5,
            ),
        )

        # Outputs
        CfnOutput(self, "RepositoryURI", value=repository.repository_uri)
        CfnOutput(self, "LoadBalancerDNS", value=alb.load_balancer_dns_name)
