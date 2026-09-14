"""The NetaGym Watch agent, built on the Strands Agents SDK.

Model-agnostic by design: the Strands agent only routes questions to tools,
so it runs on Amazon Bedrock in production (STRANDS_PROVIDER=bedrock) or on
a local Ollama model for development and demos (STRANDS_PROVIDER=ollama).
The numbers always come from the dataset, never from the model.
"""

from __future__ import annotations

import os

from strands import Agent

from .tools import ALL_TOOLS

SYSTEM_PROMPT = """You are NetaGym Watch, a civic accountability agent for Indian voters.

You answer questions about sitting Indian MPs - attendance, MPLADS fund usage,
criminal cases, declared assets, questions asked in Parliament, transparency
report cards, comparisons, and state leaderboards - using ONLY the tools
provided. You can also register a watch on an MP so the user gets a digest
and an alert when the public record changes.

Rules you never break:
1. Every number you say comes from a tool result. Never invent, estimate,
   round differently, or complete a figure from memory.
2. If a tool says there is no record for a name, say exactly that. Do not
   guess which MP the user meant; suggest they check the spelling.
3. Reply in the user's language: Hindi question, Hindi answer. Pass the
   matching language code ("en" or "hi") to every tool call.
4. Keep answers short and factual, and keep the source link the tool returns.
5. For watch requests you need a contact (email address or Telegram chat id);
   ask for it if the user has not given one.

The dataset covers all 786 sitting MPs and is built from public records:
sansad.in (attendance, questions), myneta.info sworn affidavits (criminal
cases, assets), and MPLADS fund reports.
"""


def make_model():
    provider = os.environ.get("STRANDS_PROVIDER", "bedrock").lower()
    if provider == "ollama":
        from strands.models.ollama import OllamaModel
        return OllamaModel(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.environ.get("STRANDS_MODEL_ID", "llama3.2:3b"),
        )
    if provider == "litellm":
        from strands.models.litellm import LiteLLMModel
        kwargs = {}
        if os.environ.get("STRANDS_MAX_TOKENS"):
            kwargs["params"] = {"max_tokens": int(os.environ["STRANDS_MAX_TOKENS"])}
        if os.environ.get("STRANDS_STREAM", "").lower() in ("0", "false", "no"):
            kwargs["stream"] = False
        return LiteLLMModel(
            model_id=os.environ.get("STRANDS_MODEL_ID", "ollama/llama3.2:3b"),
            **kwargs,
        )
    from strands.models.bedrock import BedrockModel
    return BedrockModel(
        model_id=os.environ.get("STRANDS_MODEL_ID", "us.amazon.nova-micro-v1:0"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def build_agent() -> Agent:
    return Agent(model=make_model(), tools=ALL_TOOLS, system_prompt=SYSTEM_PROMPT)


def ask(question: str) -> str:
    """Single-question entry point used by the demo and the eval harness."""
    result = build_agent()(question)
    return str(result)


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "What is Rahul Gandhi's attendance?"
    print(ask(q))
