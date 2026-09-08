# Neta Gym Voice

Ask any Indian MP's record by voice - attendance, fund spending, criminal
cases, assets, questions asked, transparency score - in Hindi or English.

Built for the AssemblyAI Voice Agent Hackathon (lablab.ai, Sep 2026) on the
[AssemblyAI Voice Agent API](https://www.assemblyai.com/docs/voice-agents/voice-agent-api).
The brain is deterministic: every number the agent speaks comes from this
repository's public-record JSON for all 786 MPs. The LLM only carries the
conversation; it never invents data.

## Architecture

```
caller --> AssemblyAI Voice Agent (STT -> LLM -> TTS)
                |  tool call: ask_mp_record {question}
                v
        voice/server.py  /tools/ask
                |  parse (rule-based intents, en+hi)
                v
        voice/data_index.py  ->  data/*/raw/*.json  (786 MPs)
                |  answer templates (en+hi, Indian money units, receipts)
                v
        spoken answer text -> AssemblyAI speaks it
```

- `voice/data_index.py` - slim index over per-MP public records; fuzzy
  lookup by name, alias, or constituency; state leaderboards.
- `voice/intents.py` - rule-based intent parser. English, romanized Hindi,
  and Devanagari. No LLM in the data path, same invariant as the pipeline.
- `voice/answers.py` - plain-language answer templates (Neta Gym voice: no
  jargon, numbers with receipts, party-neutral).
- `voice/server.py` - FastAPI service: web UI, `/api/ask` (text),
  `/tools/ask` (the agent's HTTP tool), voice token + agent proxy routes.
- `voice/agents/netagym-voice.jsonc` - the AssemblyAI agent definition
  (request body for `POST /v1/agents`, starter-kit format).
- `voice/publish.py` - publishes the agent to your AssemblyAI account.
- `voice/static/` - text UI (`/`) and the live call UI (`/talk`).

## Run locally (no API key needed)

```bash
pip install -e ".[api]"
PYTHONPATH=. uvicorn voice.server:app --port 8000
```

Open http://localhost:8000 and type a question. Everything except the live
voice call works offline.

## Turn on the voice

1. Create an API key at https://www.assemblyai.com/dashboard/api-keys.
2. Deploy this service somewhere public (Render, Replit, ...) and note the URL.
3. Publish the agent, pointing its tool at your deployment:

```bash
ASSEMBLYAI_API_KEY=your_key \
ASK_TOOL_URL=https://your-deployment.example.com/tools/ask \
PYTHONPATH=. python voice/publish.py
# prints the agent id; save it
```

4. Serve with the agent configured:

```bash
ASSEMBLYAI_API_KEY=your_key AGENT_ID=<id from step 3> \
PYTHONPATH=. uvicorn voice.server:app --port 8000
```

Open http://localhost:8000/talk and start the call. The browser gets a
60-second token from `/api/voice-token`; the API key never leaves the server.

## Demo script (data-complete MPs)

- "Rahul Gandhi ki haziri kaisi hai?" -> honest "no reliable source" path
- "How much MPLADS money did the Wayanad MP spend?" -> funds, crore units
- "criminal cases against the Saran MP" -> affidavit answer
- "Compare Rajiv Pratap Rudy vs Mohammad Jawed" -> head-to-head
- "best MPs in Bihar" -> state leaderboard

## Tests

```bash
PYTHONPATH=src:. pytest tests/voice -q
```
