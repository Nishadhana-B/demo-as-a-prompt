import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

from templates.guard_stack import GuardStack
from templates.serverless_api import ServerlessApiDemo


def test_demo_stack_is_tagged_and_deletable():
    app = cdk.App()
    t = Template.from_stack(ServerlessApiDemo(app, "s", demo_id="abc", expires_at="2030-01-01T00:00:00+00:00"))
    t.has_resource_properties("AWS::DynamoDB::Table", {"BillingMode": "PAY_PER_REQUEST"})
    t.has_resource("AWS::DynamoDB::Table", {"DeletionPolicy": "Delete"})
    for tag in ({"Key": "dap:managed", "Value": "true"}, {"Key": "dap:demo-id", "Value": "abc"}):
        t.has_resource_properties("AWS::DynamoDB::Table", {"Tags": Match.array_with([tag])})


def test_guard_has_reaper_schedule_and_budget():
    app = cdk.App()
    t = Template.from_stack(GuardStack(app, "g", alert_email="a@example.com"))
    t.has_resource_properties("AWS::Events::Rule", {"ScheduleExpression": "rate(15 minutes)"})
    t.resource_count_is("AWS::Budgets::Budget", 1)
    t.has_output("ExecRoleArn", {})


def test_guard_without_email_has_no_budget():
    t = Template.from_stack(GuardStack(cdk.App(), "g2"))
    t.resource_count_is("AWS::Budgets::Budget", 0)
