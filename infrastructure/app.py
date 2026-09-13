#!/usr/bin/env python3
import os

import aws_cdk as cdk
from dotenv import load_dotenv

from app_stack import AppStack
from collector_stack import CollectorStack
from deployment_bootstrap_stack import DeploymentBootstrapStack

load_dotenv()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

app = cdk.App()

bootstrap = DeploymentBootstrapStack(app, "MbtaCasinoBootstrapStack", env=env)
collector = CollectorStack(app, "MbtaCasinoCollectorStack", env=env)

cdk.Tags.of(app).add("app", "mbta-casino")
cdk.Tags.of(bootstrap).add("layer", "bootstrap")
cdk.Tags.of(collector).add("layer", "collector")

# AppStack (ALB, ECS, RDS, Redis) is paused as of 2026-09 — it cost ~$90/month while
# idle. It's only included when asked for explicitly, so `cdk deploy --all` can't
# bring it back by accident. To restore it:
#   cdk deploy MbtaCasinoAppStack -c include_app_stack=true
# See notes/2026-09-cost-reduction.md.
if app.node.try_get_context("include_app_stack") == "true":
    app_stack = AppStack(app, "MbtaCasinoAppStack", repository=bootstrap.repository, env=env)
    cdk.Tags.of(app_stack).add("layer", "app")

app.synth()
