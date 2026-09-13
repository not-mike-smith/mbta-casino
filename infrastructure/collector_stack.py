from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ssm as ssm
from constructs import Construct

COLLECTOR_CODE_DIR = Path(__file__).resolve().parent.parent / "collector"

# SecureString parameters can't be created by CloudFormation, so this one is created
# by hand (see notes/2026-09-cost-reduction.md). Parameter Store standard parameters
# are free, unlike Secrets Manager's $0.40/secret/month.
MBTA_API_KEY_PARAMETER = "/mbta-casino/mbta-api-key"


class CollectorStack(Stack):
    """
    Low-cost data collection while the betting app is paused: a Lambda that saves
    raw MBTA snapshots to S3 every minute (~$1/month vs ~$90/month for AppStack).

    Independent of AppStack — no VPC, database, or containers.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # RETAIN: the collected data outlives this stack. Delete the bucket by hand if
        # you ever really want the data gone.
        data_bucket = s3.Bucket(
            self,
            "DataBucket",
            bucket_name=f"mbta-casino-data-{self.account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        api_key_parameter = ssm.StringParameter.from_secure_string_parameter_attributes(
            self,
            "MbtaApiKey",
            parameter_name=MBTA_API_KEY_PARAMETER,
        )

        # Explicit log group so logs expire; the Lambda default keeps them forever.
        log_group = logs.LogGroup(
            self,
            "CollectorLogGroup",
            log_group_name="/lambda/mbta-casino/collector",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        collector_fn = lambda_.Function(
            self,
            "CollectorFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.handler",
            code=lambda_.Code.from_asset(str(COLLECTOR_CODE_DIR)),
            memory_size=256,
            timeout=Duration.seconds(60),
            # A retried run would save a late, mislabelled snapshot; the next minute's run is better.
            retry_attempts=0,
            log_group=log_group,
            environment={
                "DATA_BUCKET": data_bucket.bucket_name,
                "MBTA_API_KEY_PARAMETER": MBTA_API_KEY_PARAMETER,
            },
        )

        data_bucket.grant_put(collector_fn)
        api_key_parameter.grant_read(collector_fn)

        events.Rule(
            self,
            "EveryMinute",
            schedule=events.Schedule.rate(Duration.minutes(1)),
            targets=[targets.LambdaFunction(collector_fn, retry_attempts=0)],  # type: ignore[list-item]
        )

        CfnOutput(self, "DataBucketName", value=data_bucket.bucket_name)
