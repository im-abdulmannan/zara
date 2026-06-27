# Zara Architecture

## Layers

| Layer | Package | Role |
|-------|---------|------|
| Entry | `app.py` | Voice loop, wake/sleep gate |
| Cognition | `agent.py` | Intent + router + LLM fallback |
| Routing | `intent/`, `router/` | Classify and map to tools |
| Tools | `tools/registry.py` | Execute actions via runtime |
| Composition | `runtime.py` | **Single DI root** — wire all services |
| Scheduling | `automation/` | APScheduler (background thread) |
| Domains | `reminders/`, `habits/`, `meetings/`, `notes/`, `memories/` | Repository + Service + SQLite |
| Calendar | `calendar_query/` | NL schedule Q&A |
| Time | `time_parser/` | NL + clock parsing |
| Delivery | `notifications/` | TTS queue + desktop toast |
| Legacy facade | `memory/` | Conversation history + prompt summary |

## Request flow

```
Voice → STT → classify_intent → route_intent
              ├─ hit  → tool JSON → execute_tool → runtime → module
              └─ miss → LLM → tool JSON → execute_tool → runtime → module
```

Background (non-blocking): `AutomationEngine` fires reminders/habits → `NotificationWorker` → `TTSSpeaker`.

## Rules

1. **All domain access goes through `get_runtime()`** — never use module-level `_default_service()` in app code.
2. **Long-term memory writes** use `runtime.memory_service` (via `runtime.remember()` or `memory/store` facade).
3. **Time parsing** uses `time_parser.parse_when()` (NL first, clock fallback).
4. **New tools**: add handler in `tools/registry.py`, optional intent in `intent/models.py` + `router/intent_router.py`.

## SQLite databases

- `zara_reminders.sqlite`, `zara_habits.sqlite`, `zara_meetings.sqlite`
- `zara_notes.sqlite`, `zara_memories.sqlite`, `zara_automation.sqlite` (APScheduler job store)
