"""Amazon Bedrock AgentCore Runtime entrypoint.

Local test:  python agentcore_app.py   then   curl -X POST localhost:8080/invocations -d '{"prompt":"..."}'
Deploy:      agentcore configure --entrypoint agentcore_app.py --requirements-file requirements.txt && agentcore deploy
The runtime keeps the agent (and its message history) in memory per session.
"""
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agent.main import build_agent

app = BedrockAgentCoreApp()
_agent = None


@app.entrypoint
def invoke(payload, context=None):
    global _agent
    _agent = _agent or build_agent()
    result = _agent(payload.get("prompt", "What demos can you build?"))
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
