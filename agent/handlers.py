"""Source code of the demo Lambdas. Each template defines app(event) -> (status, dict).

WRAPPER adds the soft TTL: after DAP_EXPIRES_AT the function answers 410 Gone.
Events are Lambda Function URL (payload v2) events.
"""

WRAPPER = '''
import base64, datetime as dt, json, os, re

def _resp(status, body):
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}

def handler(event, context):
    if dt.datetime.now(dt.timezone.utc) >= dt.datetime.fromisoformat(os.environ["DAP_EXPIRES_AT"]):
        return _resp(410, {"error": "demo expired", "demo_id": os.environ["DAP_DEMO_ID"]})
    status, body = app(event)
    return _resp(status, body)

def _json_body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    return json.loads(raw)
'''

HELLO_API = '''
def app(event):
    http = event["requestContext"]["http"]
    return 200, {
        "message": "Hello from a Demo-as-a-Prompt demo",
        "demo_id": os.environ["DAP_DEMO_ID"],
        "expires_at": os.environ["DAP_EXPIRES_AT"],
        "method": http["method"],
        "path": event.get("rawPath", "/"),
    }
'''

TEXT_TOOLKIT = '''
def app(event):
    http = event["requestContext"]["http"]
    path = event.get("rawPath", "/").rstrip("/") or "/"
    if http["method"] == "GET":
        return 200, {"endpoints": ["POST /wordcount", "POST /slugify", "POST /base64"], "body": {"text": "string"}}
    text = _json_body(event).get("text", "")
    if path == "/wordcount":
        return 200, {"words": len(text.split()), "chars": len(text)}
    if path == "/slugify":
        return 200, {"slug": re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")}
    if path == "/base64":
        return 200, {"base64": base64.b64encode(text.encode()).decode()}
    return 404, {"error": "unknown path", "path": path}
'''

UNIT_CONVERTER = '''
LENGTH = {"m": 1.0, "km": 1000.0, "cm": 0.01, "mi": 1609.344, "ft": 0.3048, "in": 0.0254}

def app(event):
    http = event["requestContext"]["http"]
    if http["method"] == "GET":
        return 200, {"endpoints": ["POST /temperature", "POST /length"],
                     "temperature": {"value": 100, "from": "C", "to": "F"},
                     "length": {"value": 5, "from": "km", "to": "mi"}}
    b = _json_body(event)
    path = event.get("rawPath", "/").rstrip("/")
    if path == "/temperature":
        v, f, t = float(b["value"]), b["from"].upper(), b["to"].upper()
        c = {"C": v, "F": (v - 32) * 5 / 9, "K": v - 273.15}[f]
        out = {"C": c, "F": c * 9 / 5 + 32, "K": c + 273.15}[t]
        return 200, {"result": round(out, 4), "unit": t}
    if path == "/length":
        v = float(b["value"])
        return 200, {"result": round(v * LENGTH[b["from"]] / LENGTH[b["to"]], 6), "unit": b["to"]}
    return 404, {"error": "unknown path", "path": path}
'''

SOURCES = {"hello-api": HELLO_API, "text-toolkit": TEXT_TOOLKIT, "unit-converter": UNIT_CONVERTER}


def build_source(template_id: str) -> str:
    return WRAPPER + SOURCES[template_id]
