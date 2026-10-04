# Zara

Zara is a Windows desktop AI assistant. Start the app, type what you want in plain English, and Zara uses an LLM plus local tools to open apps, search files, and control the system.

## Features

- **Text mode** — run `python app.py`, type at the `You>` prompt, press Enter
- **Agent loop (today)** — one turn: think → pick tool(s) or chat → execute on Windows
- **Multi-step tasks** — work plan → SerpAPI research → synthesis → `document` save ([ARCHITECTURE.md](ARCHITECTURE.md))
- **Web search** — `web_search` via [SerpAPI](https://serpapi.com/) (`SERPAPI_API_KEY`)
- **Optional intent routing** — Gemini (or another provider) can fast-path common requests
- **Capability tools** — `filesystem`, `document`, `system`, `application`, `clipboard`, `web_search` (plus legacy granular tools)

## Requirements

- **Windows 10/11**
- **Python 3.11+**
- API keys (see `.env.example`):
  - [OpenRouter](https://openrouter.ai/) — main LLM
  - [Google Gemini](https://aistudio.google.com/apikey) — optional intent classification

## Setup

```powershell
git clone https://github.com/YOUR_USERNAME/zara.git
cd zara
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

## Usage

```text
You> find the zara folder from drive D
Zara: Opening folder D:\zara.
```

Type `quit` or press `Ctrl+C` to exit.

## Request flow (current)

```
You> prompt → Planner (single turn) → ask_agent → tools → reply
```

Target: **WorkPlan** → agent loop (step → observe → re-plan) → **capabilities** (filesystem, web_search, …). See [ARCHITECTURE.md](ARCHITECTURE.md).

## Project structure

```
zara/
├── app.py          # Entry point (text mode)
├── agent.py        # LLM + intent pipeline
├── config.py       # Env config
├── brain/          # Planner and fast-path reasoning
├── core/           # Session, task state, guardrails, logging
├── intent/         # Intent classifier
├── router/         # Intent → tool routing
├── tools/          # Tool registry and Windows handlers
├── memory/         # Conversation history (JSON, for LLM context)
└── tests/
```

## Testing

```powershell
pip install pytest
python -m pytest tests/ -v
```

## License

MIT
