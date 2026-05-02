from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_ecr as ecr
from constructs import Construct


class DeploymentBootstrapStack(Stack):
    """
    Long-lived infrastructure that must exist before any deployment can run.
    Deploy this once; it rarely changes.

    Currently contains:
    - ECR repository (stores Docker images pushed by the deploy process)
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # RETAIN so the repo (and any pushed images) survive a stack teardown.
        self.repository = ecr.Repository(
            self,
            "Repository",
            repository_name="mbta-casino",
            removal_policy=RemovalPolicy.RETAIN,
        )
