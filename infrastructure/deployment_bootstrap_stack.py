from aws_cdk import Stack
from aws_cdk import aws_ecr as ecr
from constructs import Construct


class DeploymentBootstrapStack(Stack):
    """
    Long-lived infrastructure that must exist before any deployment can run.
    Deploy this once; it rarely changes.

    Currently contains:
    - ECR repository (stores Docker images pushed by the deploy process)

    The ECR repository is looked up by name rather than created, so this stack
    is safe to deploy even if the repository already exists (e.g. after a stack
    teardown that retained the repo).
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.repository = ecr.Repository.from_repository_name(
            self,
            "Repository",
            repository_name="mbta-casino",
        )
