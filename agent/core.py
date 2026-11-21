"""Deploy / validate / reap logic (sandbox edition: Lambda + Function URL, boto3 only).

Plain functions so tests and the Strands tools share them.
"""
import datetime as dt
import io
import json
import os
import time
import urllib.error
import urllib.request
import uuid
import zipfile

import boto3

from .catalog import TEMPLATES, clamp_ttl, get_template
from .handlers import build_source

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2"
ROLE_NAME = os.environ.get("DAP_LAMBDA_ROLE", "DemoToolLambdaRole")
PREFIX = "dap-"


def _lambda():
    return boto3.client("lambda", region_name=REGION)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def new_demo_id() -> str:
    return uuid.uuid4().hex[:6]


def function_name(demo_id: str, template_id: str) -> str:
    return f"{PREFIX}{demo_id}-{template_id}"


def is_expired(expires_at_iso: str, now: dt.datetime | None = None) -> bool:
    return dt.datetime.fromisoformat(expires_at_iso) <= (now or _now())


def _zip(source: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.py", source)
    return buf.getvalue()


def estimate_cost(template_id: str, ttl_hours: int | None = None) -> dict:
    t = get_template(template_id)
    h = clamp_ttl(ttl_hours)
    return {"template": t.id, "ttl_hours": h, "idle_cost_usd": 0.0,
            "usd_per_million_requests": t.est_usd_per_million_requests,
            "note": "Lambda has no idle cost. You pay only per request."}


def deploy(template_id: str, ttl_hours: int | None = None, demo_id: str | None = None) -> dict:
    t = get_template(template_id)  # raises for anything not in the catalog
    demo_id = demo_id or new_demo_id()
    hours = clamp_ttl(ttl_hours)
    expires = (_now() + dt.timedelta(hours=hours)).isoformat()
    name = function_name(demo_id, t.id)
    lam = _lambda()
    role_arn = boto3.client("iam").get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
    reap_expired()  # lazy sweep: no scheduler is available in the sandbox
    lam.create_function(
        FunctionName=name, Runtime="python3.12", Handler="index.handler", Role=role_arn,
        Code={"ZipFile": _zip(build_source(t.id))}, Timeout=10, MemorySize=128,
        Environment={"Variables": {"DAP_EXPIRES_AT": expires, "DAP_DEMO_ID": demo_id}},
        Tags={"dap:managed": "true", "dap:demo-id": demo_id, "dap:template": t.id, "dap:expires-at": expires},
    )
    lam.get_waiter("function_active_v2").wait(FunctionName=name)
    url = lam.create_function_url_config(FunctionName=name, AuthType="NONE")["FunctionUrl"]
    # A public Function URL needs BOTH permissions.
    lam.add_permission(FunctionName=name, StatementId="url-public", Action="lambda:InvokeFunctionUrl",
                       Principal="*", FunctionUrlAuthType="NONE")
    lam.add_permission(FunctionName=name, StatementId="url-invoke", Action="lambda:InvokeFunction",
                       Principal="*", InvokedViaFunctionUrl=True)
    return {"ok": True, "demo_id": demo_id, "template": t.id, "ttl_hours": hours,
            "expires_at": expires, "url": url}


def _call(url: str, method: str = "GET", body: dict | None = None, retries: int = 6):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    last = None
    for _ in range(retries):  # a new Function URL can take a few seconds to become reachable
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 403:
                return e.code, json.loads(e.read() or b"{}")
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(3)
    raise RuntimeError(f"unreachable: {last}")


def validate(url: str, template_id: str) -> dict:
    """Smoke-test a deployed demo. Returns pass/fail and latency."""
    t0 = time.time()
    try:
        if template_id == "text-toolkit":
            status, out = _call(url.rstrip("/") + "/wordcount", "POST", {"text": "one two three"})
            ok = status == 200 and out.get("words") == 3
        elif template_id == "unit-converter":
            status, out = _call(url.rstrip("/") + "/temperature", "POST", {"value": 100, "from": "C", "to": "F"})
            ok = status == 200 and out.get("result") == 212.0
        else:
            status, out = _call(url)
            ok = status == 200 and "demo_id" in out
        return {"ok": ok, "http_status": status, "latency_ms": int((time.time() - t0) * 1000), "response": out}
    except Exception as e:  # noqa: BLE001 - report any failure to the agent
        return {"ok": False, "error": str(e)}


def list_demos() -> list[dict]:
    out = []
    for page in _lambda().get_paginator("list_functions").paginate():
        for f in page["Functions"]:
            env = (f.get("Environment") or {}).get("Variables", {})
            if f["FunctionName"].startswith(PREFIX) and "DAP_EXPIRES_AT" in env:
                out.append({"function": f["FunctionName"], "arn": f["FunctionArn"],
                            "demo_id": env.get("DAP_DEMO_ID"), "expires_at": env["DAP_EXPIRES_AT"]})
    return out


def _delete_if_managed(d: dict) -> bool:
    lam = _lambda()
    if lam.list_tags(Resource=d["arn"]).get("Tags", {}).get("dap:managed") != "true":
        return False  # never touch functions we do not own
    lam.delete_function(FunctionName=d["function"])
    return True


def teardown(demo_id: str) -> dict:
    """Delete every managed function for this demo id."""
    gone = [d["function"] for d in list_demos() if d["demo_id"] == demo_id and _delete_if_managed(d)]
    return {"ok": bool(gone), "deleted": gone}


def reap_expired() -> dict:
    """Delete all expired demos. Called on every deploy and available as an agent tool."""
    now = _now()
    gone = [d["function"] for d in list_demos() if is_expired(d["expires_at"], now) and _delete_if_managed(d)]
    return {"reaped": gone}


__all__ = ["TEMPLATES", "deploy", "validate", "list_demos", "teardown", "reap_expired", "estimate_cost"]
