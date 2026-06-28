# Zara

Zara is a voice-first desktop AI assistant for Windows. Say a wake phrase, speak a command, and Zara routes your request through intent classification and tools — with an LLM fallback when needed.

The voice loop is driven by an event-driven orchestrator (`core/`) that handles wake-word detection, VAD capture, planning, and TTS. Domain services (reminders, habits, notes, and more) are wired through a single composition root (`runtime.py`).

## Features

### Voice

- **Wake word detection** — "Hey Zara", "Hello Zara", "Zara", and custom phrases
- **Sleep phrases** — "Sleep Zara", "Go to sleep", etc.
- **Speech-to-text** — faster-whisper
- **Text-to-speech** — pyttsx3 replies
- **VAD capture** — records when you speak, not on a fixed timer
- **Continuous conversation** — after wake, stay in a multi-turn session until you say sleep or time out (configurable via `CONTINUOUS_CONVERSATION`)

### Cognition

- **Intent classification** — Gemini-based fast routing (15 intents)
- **Intent router** — dispatches directly to tools when confidence is high
- **LLM fallback** — OpenRouter with a model fallback chain
- **Planner** — parses LLM JSON, runs tools, speaks the result
- **Auto memory capture** — saves names, tasks, and preferences from natural speech

### Tools (39 registered)

| Category | Examples |
|----------|----------|
| Applications | open, close, search installed apps |
| Browser | open website, launch URL, Google search |
| Filesystem | create/open folder, search, copy, move, rename, delete |
| System | time, lock, shutdown, restart, sleep, volume, brightness, screenshot, clipboard |
| Domain | reminders, habits, meetings, notes, memories, calendar queries |

### Persistence & scheduling

- **Reminders** — one-time or recurring, with spoken + toast notifications
- **Habits** — recurring tracking with streaks, pause/resume
- **Meetings** — schedule and query appointments
- **Notes** — create, list, search
- **Memories** — long-term facts, name, preferences (SQLite)
- **Calendar queries** — natural-language schedule Q&A ("what do I have today?")
- **Automation** — APScheduler background jobs for reminders and habits

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design.

## Requirements

- **Windows 10/11**
- **Python 3.11+**
- A microphone and speakers
- API keys:
  - [OpenRouter](https://openrouter.ai/) — main LLM
  - [Google Gemini](https://aistudio.google.com/apikey) — intent classification

## Setup

1. **Clone the repository**

   ```powershell
   git clone https://github.com/YOUR_USERNAME/zara.git
   cd zara
   ```

2. **Create a virtual environment**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**

   ```powershell
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   ```powershell
   copy .env.example .env
   ```

   Edit `.env` and add your API keys.

5. **Run Zara**

   ```powershell
   python app.py
   ```

## Usage

1. Zara starts and says hello.
2. Say a wake phrase: **"Hey Zara"**, **"Hello Zara"**, or **"Zara"**.
3. Zara replies **"I'm listening."** — speak your command.
4. Follow-up commands do not require the wake word again (continuous mode is on by default).
5. Say **"Sleep Zara"** or **"Go to sleep"** to return to wake-word mode.
6. Press `Ctrl+C` to shut down.

## Request flow

```
Wake word → VAD capture → STT → Planner
                                  └─ ask_agent (intent classify → route or LLM)
                                       └─ tools → runtime → domain services
                                            └─ TTS reply
```

Background (non-blocking): `AutomationEngine` fires reminders/habits → `NotificationWorker` → `TTSSpeaker`.

## Project structure

```
zara/
├── app.py              # Entry point — starts runtime + voice orchestrator
├── agent.py            # LLM + intent pipeline
├── runtime.py          # Composition root (DI for all services)
├── config.py           # Top-level env config (wake word, API keys)
├── core/               # Orchestrator, state machine, event bus, session
├── brain/              # Planner and agent wrapper
├── voice/              # STT, TTS, VAD, wake word, audio
├── intent/             # Gemini intent classifier
├── router/             # Intent → tool routing
├── tools/              # Tool registry, executor, domain/system handlers
├── reminders/          # Reminder service + scheduler
├── habits/             # Habit tracking
├── meetings/           # Meeting storage
├── notes/              # Notes service
├── memories/           # Long-term memory (SQLite)
├── memory/             # Conversation history + short-term tasks (JSON)
├── automation/         # APScheduler engine
├── notifications/      # TTS queue + desktop toasts
├── calendar_query/     # Natural-language schedule queries
├── time_parser/        # NL + clock time parsing
└── tests/              # Pytest suite (99 tests)
```

## Testing

Install pytest, then run the suite:

```powershell
pip install pytest
python -m pytest tests/ -v
```

Tests use isolated temporary SQLite databases and a headless speaker — no microphone, speakers, or API keys required. Coverage includes wake-word detection, state machine, intent routing, time parsing, domain services, tool registry, planner (LLM mocked), and filesystem tools.

Live integration (Whisper, TTS, Gemini, OpenRouter, Windows system tools) is not automated and should be verified manually.

## Local data

Zara creates SQLite databases and JSON memory files in the project directory at runtime:

- `zara_reminders.sqlite`, `zara_habits.sqlite`, `zara_meetings.sqlite`
- `zara_notes.sqlite`, `zara_memories.sqlite`, `zara_automation.sqlite`
- `memory/history.json`, `memory/short_term.json`

These are excluded from git via `.gitignore` and are not pushed to GitHub.

## License

MIT
