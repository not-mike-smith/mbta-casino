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

bootstrap = DeploymentBootstrapStack(app, "MbtaCasinoBootstrapStack", env=env)
app_stack = AppStack(app, "MbtaCasinoAppStack", repository=bootstrap.repository, env=env)

cdk.Tags.of(app).add("app", "mbta-casino")
cdk.Tags.of(bootstrap).add("layer", "bootstrap")
cdk.Tags.of(app_stack).add("layer", "app")

app.synth()
