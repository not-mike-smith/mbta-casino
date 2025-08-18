#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import aws_cdk as cdk

from infrastructure.infrastructure_stack import InfrastructureStack

load_dotenv()

app = cdk.App()
InfrastructureStack(
    app,
    "InfrastructureStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
)

app.synth()
