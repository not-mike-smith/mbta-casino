#!/usr/bin/env python3
import os

import aws_cdk as cdk
from dotenv import load_dotenv

from app_stack import AppStack
from deployment_bootstrap_stack import DeploymentBootstrapStack

load_dotenv()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

app = cdk.App()

bootstrap = DeploymentBootstrapStack(app, "DeploymentBootstrapStack", env=env)

AppStack(app, "AppStack", repository=bootstrap.repository, env=env)

app.synth()
