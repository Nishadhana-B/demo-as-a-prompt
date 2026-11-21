from aws_cdk import CfnOutput, RemovalPolicy, Stack, Tags
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_lambda as _lambda
from constructs import Construct

HANDLER = """
import json, os, uuid, boto3
t = boto3.resource("dynamodb").Table(os.environ["TABLE"])
def handler(event, ctx):
    m = event["httpMethod"]
    if m == "POST":
        item = {"id": str(uuid.uuid4()), **json.loads(event.get("body") or "{}")}
        t.put_item(Item=item)
        return {"statusCode": 201, "body": json.dumps(item)}
    if m == "GET" and event.get("pathParameters"):
        r = t.get_item(Key={"id": event["pathParameters"]["proxy"]}).get("Item")
        return {"statusCode": 200 if r else 404, "body": json.dumps(r or {})}
    return {"statusCode": 200, "body": json.dumps(t.scan(Limit=25)["Items"])}
"""


class ServerlessApiDemo(Stack):
    def __init__(self, scope: Construct, id: str, *, demo_id: str, expires_at: str, **kw):
        super().__init__(scope, id, **kw)
        table = ddb.Table(
            self, "Items",
            partition_key=ddb.Attribute(name="id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # demos must delete cleanly
        )
        fn = _lambda.Function(
            self, "Fn", runtime=_lambda.Runtime.PYTHON_3_12, handler="index.handler",
            code=_lambda.Code.from_inline(HANDLER), environment={"TABLE": table.table_name},
        )
        table.grant_read_write_data(fn)
        api = apigw.LambdaRestApi(
            self, "Api", handler=fn,
            deploy_options=apigw.StageOptions(throttling_rate_limit=20, throttling_burst_limit=40),
        )
        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "TableName", value=table.table_name)
        Tags.of(self).add("dap:managed", "true")
        Tags.of(self).add("dap:demo-id", demo_id)
        Tags.of(self).add("dap:expires-at", expires_at)
