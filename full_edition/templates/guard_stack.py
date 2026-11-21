"""Always-on guardrails: TTL reaper, CloudFormation execution role, monthly budget."""
from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from constructs import Construct

REAPER_SRC = (Path(__file__).parent.parent / "guard" / "reaper" / "index.py").read_text()


class GuardStack(Stack):
    def __init__(self, scope: Construct, id: str, *, alert_email: str | None = None,
                 monthly_budget_usd: float = 25, dry_run: bool = False, **kw):
        super().__init__(scope, id, **kw)

        # Demo stacks deploy through this role, so the reaper (and the agent)
        # only need cloudformation:* + iam:PassRole, never the underlying service rights.
        self.exec_role = iam.Role(
            self, "DemoExecRole", assumed_by=iam.ServicePrincipal("cloudformation.amazonaws.com"),
            description="Used by CloudFormation to create/delete demo stacks",
        )
        # TODO(hardening): add a permissions boundary and scope IAM actions to dap-* roles.
        self.exec_role.add_to_policy(iam.PolicyStatement(
            actions=["apigateway:*", "lambda:*", "dynamodb:*", "logs:*", "iam:*Role*",
                     "iam:*RolePolicy", "iam:PassRole", "iam:TagRole", "iam:UntagRole"],
            resources=["*"],
        ))

        CfnOutput(self, "ExecRoleArn", value=self.exec_role.role_arn)

        fn = _lambda.Function(
            self, "Reaper", runtime=_lambda.Runtime.PYTHON_3_12, handler="index.handler",
            code=_lambda.Code.from_inline(REAPER_SRC), timeout=Duration.minutes(2),
            environment={"DRY_RUN": str(dry_run).lower()},
        )
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["cloudformation:DescribeStacks", "cloudformation:DeleteStack"], resources=["*"]))
        fn.add_to_role_policy(iam.PolicyStatement(actions=["iam:PassRole"], resources=[self.exec_role.role_arn]))
        events.Rule(self, "Every15Min", schedule=events.Schedule.rate(Duration.minutes(15))
                    ).add_target(targets.LambdaFunction(fn))

        if alert_email:
            budgets.CfnBudget(
                self, "MonthlyBudget",
                budget=budgets.CfnBudget.BudgetDataProperty(
                    budget_type="COST", time_unit="MONTHLY",
                    budget_limit=budgets.CfnBudget.SpendProperty(amount=monthly_budget_usd, unit="USD")),
                notifications_with_subscribers=[budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        notification_type="ACTUAL", comparison_operator="GREATER_THAN",
                        threshold=80, threshold_type="PERCENTAGE"),
                    subscribers=[budgets.CfnBudget.SubscriberProperty(
                        subscription_type="EMAIL", address=alert_email)])],
            )
