#!/usr/bin/env python3
"""CDK entrypoint. Context: demo_id, ttl_hours, alert_email, dry_run."""
import datetime as dt

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import aws_cdk as cdk

from agent.catalog import clamp_ttl
from templates.guard_stack import GuardStack
from templates.serverless_api import ServerlessApiDemo

app = cdk.App()
ctx = app.node.try_get_context

GuardStack(app, "DapGuard", alert_email=ctx("alert_email"), dry_run=ctx("dry_run") == "true")

demo_id = ctx("demo_id") or "local"
expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=clamp_ttl(ctx("ttl_hours")))).isoformat()
ServerlessApiDemo(app, f"dap-{demo_id}-serverless-api", demo_id=demo_id, expires_at=expires)

app.synth()
