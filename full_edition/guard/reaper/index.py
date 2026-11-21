"""TTL reaper: deletes expired demo stacks. Inlined into Lambda (keep < 4 KB)."""
import datetime as dt
import os

import boto3

cfn = boto3.client("cloudformation")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"


def is_expired(tags, now):
    t = {x["Key"]: x["Value"] for x in tags or []}
    if t.get("dap:managed") != "true" or "dap:expires-at" not in t:
        return False  # never touch stacks we do not own
    return dt.datetime.fromisoformat(t["dap:expires-at"]) <= now


def handler(event, context):
    now = dt.datetime.now(dt.timezone.utc)
    deleted = []
    for page in cfn.get_paginator("describe_stacks").paginate():
        for s in page["Stacks"]:
            if s["StackStatus"].endswith("IN_PROGRESS") or "DELETE" in s["StackStatus"]:
                continue
            if is_expired(s.get("Tags"), now):
                deleted.append(s["StackName"])
                if not DRY_RUN:
                    cfn.delete_stack(StackName=s["StackName"])
    print({"dry_run": DRY_RUN, "reaped": deleted})
    return {"reaped": deleted}
