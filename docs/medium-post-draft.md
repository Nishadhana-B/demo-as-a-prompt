# I let an AI agent build my AWS demo environments (and made sure they delete themselves)

*Draft. Screenshots are in the `demo-as-a-prompt-screenshots` folder; file names are noted in brackets.*

Anyone who does demos on AWS knows the routine: build a quick API or app for a customer call, then forget to delete it. I wanted to see if an agent could do the boring parts safely, so I built **Demo-as-a-Prompt**: you ask in plain English, and an agent deploys a demo, tests it, and cleans it up.

> "Spin up a text toolkit API demo for 2 hours for a customer call, and tell me when it expires."

[00-architecture-diagram.png]

## The one design rule: the model never writes infrastructure

The agent (Strands Agents on Amazon Bedrock, Claude Sonnet 4.5) doesn't generate code or templates. It picks from a small **catalog of vetted templates** and sets a time to live (TTL). Anything not in the catalog is rejected, and every demo gets a TTL, capped at 72 hours.

Its tools are small and boring on purpose: `list_templates`, `estimate_cost`, `deploy_demo`, `validate_demo`, `list_demos`, `teardown_demo`, and `reap_expired`. The system prompt forces an order: estimate the cost, deploy, then validate and report.

## What a run looks like

[02-agent-run-transcript.txt, 09-e2e-recheck-agent-transcript.txt]

The agent lists templates, states the cost, deploys a Lambda function with a public Function URL, calls it to check it works (HTTP 200 in about 1.3 seconds), and reports the URL and expiry time.

[03-lambda-console-agent-created-demo.jpg, 04-lambda-function-overview-function-url.jpg, 06-live-demo-url-in-browser.jpg]

Every demo is tagged `dap:managed`, `dap:demo-id`, `dap:template` and `dap:expires-at`. The cleanup code only ever touches resources carrying `dap:managed=true`.

[05-lambda-tags-ttl-metadata.jpg]

## Cleaning up: a TTL that works without a scheduler

I built this in an AWS Builder Center sandbox. Those accounts are great for learning, but they deny CloudFormation, DynamoDB, API Gateway, EventBridge and IAM writes. My first design (CDK, API Gateway, DynamoDB, an EventBridge-driven reaper) simply could not deploy there.

So I redesigned around what the sandbox allows: Lambda, Function URLs and Bedrock. With no scheduler, the TTL became two layers:

1. **Soft TTL.** Each demo checks its own expiry on every request and answers **HTTP 410 Gone** once it has passed.
2. **Reaping.** A `reap_expired` tool deletes expired demos, and `deploy_demo` calls it first, so cleanup happens as a side effect of normal use.

I tested it by forcing a demo to expire: the next request returned `{"error": "demo expired"}`, then the reaper deleted it and the console showed no demos left.

[07-ttl-expiry-and-reaper-transcript.txt, 08-lambda-console-after-reap-empty.jpg]

## Running it as an AgentCore app

The agent is wrapped in a Bedrock AgentCore Runtime entrypoint (`agentcore_app.py`). I tested it with AgentCore's local server: `/ping` reports healthy, `/invocations` runs the agent, and a second call in the same session remembered which demo the first call had created and tore it down.

[10-agentcore-local-invocation-transcript.txt]

I could not deploy it to AgentCore Runtime from the sandbox, because it has no writable S3 bucket and denies ECR and CodeBuild. The deploy commands are in the README for a normal account.

## Honest limitations

- The TTL is soft: an expired demo stops answering immediately but is deleted only on the next deploy or reap call.
- Function URLs are public and the templates are stateless.
- There are only three templates (hello API, text toolkit, unit converter).
- A full CDK edition exists in the repo (API Gateway, DynamoDB, EventBridge reaper, budget alarm). It passes `cdk synth` and unit tests, but I have not deployed it.
- In one run the agent answered a conversion from the validation result instead of calling the API again, so the prompt could be stricter.

## What I learned

- Constraining the model to a catalog is a much better safety story than trying to review generated infrastructure.
- Tags make cleanup safe: "only delete what I created" is one condition.
- A public Lambda Function URL needs **two** resource-policy statements, `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` with the invoked-via-function-url condition, or you get a confusing 403. The AWS CLI I used had no flag for the second one, so I used boto3.
- Designing for the environment you actually have beats designing for the one you wish you had.

Code: *(add your GitHub link here)*
