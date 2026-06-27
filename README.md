# Zara

Zara is a voice-first desktop AI assistant for Windows. Say a wake phrase, speak a command, and Zara routes your request through intent classification and tools — with an LLM fallback when needed.

## Features

- **Voice interaction** — wake word detection, speech-to-text (Whisper), text-to-speech replies
- **Intent routing** — fast Gemini-based classification with tool execution
- **Tools** — open apps, browse the web, manage files, system commands, and more
- **Reminders & habits** — scheduled notifications with spoken alerts
- **Notes, meetings, memories** — persistent SQLite-backed storage
- **Automation** — background scheduler for timed tasks

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
4. Say **"Sleep Zara"** or **"Go to sleep"** to return to wake-word mode.
5. Press `Ctrl+C` to shut down.

## Project structure

```
zara/
├── app.py              # Main voice loop
├── agent.py            # LLM + intent pipeline
├── runtime.py          # Service composition root
├── voice/              # STT, TTS, VAD, session
├── intent/             # Intent classifier
├── router/             # Intent → tool routing
├── tools/              # Tool registry and executors
├── reminders/          # Reminder service
├── habits/             # Habit tracking
├── meetings/           # Meeting storage
├── notes/              # Notes service
├── memories/           # Long-term memory
├── automation/         # Background scheduler
├── notifications/      # TTS queue + desktop toasts
└── calendar_query/     # Natural-language schedule queries
```

## Local data

Zara creates SQLite databases and JSON memory files in the project directory at runtime. These are excluded from git via `.gitignore` and are not pushed to GitHub.

## License

MIT
