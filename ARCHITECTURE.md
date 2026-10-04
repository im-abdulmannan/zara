# Zara Architecture

Zara is an **OS-first, plan-first** Windows agent. The LLM decides strategy; the **Planner** structures work; the **Agent loop** executes one step at a time, observes results, and may re-plan. Side effects go through a **small set of high-level capabilities**, not dozens of low-level tool names exposed to the model.

**Browser automation** is intentionally **out of scope** for OS Agent v1. External information enters through **web search ([SerpAPI](https://serpapi.com/))** via the `web_search` tool and local files/apps. A future **Browser** capability can plug in without redesigning this stack.

## Roles

| Component | Responsibility |
|-----------|----------------|
| **Planner** | Understand goal, context, and produce or update a **work plan** (WHAT + HOW) |
| **Agent loop** | Execute the current plan step, observe, reason, re-plan when needed |
| **Capabilities** | High-level OS / knowledge / output surfaces (filesystem, document, system, …) |
| **Permission manager** | Gate risky operations before the tool executor runs |
| **Task state** | Goal, plan, current step, observations, files touched, errors (separate from chat history) |
| **Conversation memory** | `memory/history.json` — LLM context only |

```text
                         USER
                           │
                           ▼
                    ┌─────────────┐
                    │   PLANNER   │  goal + structured WorkPlan
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ AGENT LOOP  │  execute → observe → reason → re-plan?
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        CAPABILITIES   GUARDRAILS   TASK STATE
              │
              ▼
     Files / Windows / SerpAPI / Email / …
```

Dynamic planning (target behavior):

```text
PLAN → EXECUTE STEP → OBSERVE → REASON → (re-plan?) → NEXT STEP → DONE
```

## Capability layer (target, ~6–8 surfaces)

Each capability wraps multiple internal operations. The agent reasons at capability level, not raw Win32/API granularity.

| Capability | Operations (internal) | v1 status |
|------------|----------------------|-----------|
| **filesystem** | search, read, write, copy, move, delete | Partial — `filesystem` capability + granular tools |
| **document** | read/create/append TXT; DOCX with `python-docx` | **Done** — `tools/capabilities/document.py` |
| **system** | time, lock, sleep, power, volume, brightness, screenshot | **Done** — `tools/capabilities/system.py` |
| **application** | open, close, search installed | **Done** — `tools/capabilities/application.py` |
| **clipboard** | read, write | **Done** — `tools/capabilities/clipboard.py` |
| **web_search** | `search(query)` via SerpAPI | **Done** — `tools/web_search.py` |
| **email** | search, read, draft, send, attach | Planned |
| **terminal** | `execute_command` (heavily gated) | Planned |

Today’s registry still exposes **granular tools** (e.g. `search_files`, `copy_file`). Consolidation into capability facades is **Phase 2**; the architecture above is the consolidation target.

## Permission model

```text
Agent → GuardrailManager (Permission) → ToolRegistry.execute → OS
```

- Reads / low-risk creates: automatic where safe  
- Deletes, power actions, shell, send email: confirmation (extend `core/guardrails.py`)  
- Tool metadata: `requires_confirmation` on `BaseTool`

## Data models

| Model | Module | Purpose |
|-------|--------|---------|
| `WorkPlan` / `WorkStep` | `core/work_plan.py` | Strategic steps before tool calls |
| `TaskState` | `core/task_state.py` | Running task: plan, current step, observations |
| `ExecutionPlan` | `tools/executor.py` | Concrete tool steps for **one** agent turn |
| `Session` | `core/session.py` | Turn history + optional `task_state` |

Example task state (conceptual):

```json
{
  "goal": "Create AI assignment",
  "status": "running",
  "current_step_id": 4,
  "completed_step_ids": [1, 2, 3],
  "plan": { "goal": "...", "steps": [{ "id": 1, "task": "Research topic" }] }
}
```

## Current implementation (single-turn)

What runs in `python app.py` today:

```text
User → brain.planner.Planner.plan_and_execute
         → agent.ask_agent (reason → intent route → LLM JSON)
         → tools.executor.execute_plan (one batch of tools)
         → spoken reply
```

| Layer | Package | Role today |
|-------|---------|------------|
| Entry | `app.py` | Text REPL |
| Turn planner | `brain/planner.py` | One user message → one LLM decision → tools |
| Cognition | `agent.py` | Reasoning, intent hint, LLM tool JSON |
| Routing | `intent/`, `router/` | Optional fast-path to a tool |
| Tools | `tools/` | Granular Windows tools |
| Memory | `memory/memory.py` | Conversation for LLM context |
| Safety | `core/guardrails.py` | High-risk confirmation |

**Implemented:** strategic planner, agent loop, SerpAPI `web_search`, `brain/replan.py` (after research steps), `core/task_store.py` (`memory/task_state.json`), `filesystem` capability facade. Simple commands still use the single-turn path.

**Gap vs target:** PDF support, email/terminal capabilities, richer deliverable path extraction from tool results.

## Development phases

**Phase 1 — Agent core**

1. Unified capability interface — **partial** (`tools/capabilities/`, registry prompt)  
2. Strategic planner → `WorkPlan` (JSON) — **done**  
3. Agent execution loop over steps — **done**  
4. Step observation handling — **done**  
5. Dynamic re-planning after observations — **done** (`brain/replan.py`)  
6. Persist `TaskState` — **done** (`memory/task_state.json`)

**Phase 2 — OS**

7. Filesystem capability facade — **done**  
8. Document capability — **done**  
9. System / application / clipboard facades — **done**  

**Phase 3 — Intelligence**

12. SerpAPI `web_search` — **done**  
13. Multi-query research + synthesis — **done** (`brain/research.py`, follow-up query hints)  
14. Research → document generation — **done** (auto-synthesis before write steps, `document` capability)  

**Phase 4 — Communication**

15. Email capability (draft → approve → send)  

**Phase 5 — Safety**

18. Permission tiers per capability/action  
19. Confirmation UX (text + future voice)  
20. Audit / execution log  

## Adding behavior

1. **New OS behavior:** implement handler under `tools/`, register with `@register_tool`, then (Phase 2+) expose via the right capability facade.  
2. **New external info:** extend SerpAPI-backed `web_search` — not browser automation.  
3. **New intents (optional):** extend `intent/models.py` and `router/intent_router.py` for fast-path only; strategic planning remains planner-owned.

## Rules (unchanged)

1. Side effects go through `tools/` — never direct OS calls from the LLM.  
2. The model returns structured JSON; executors run handlers.  
3. Chat history is not a substitute for `TaskState` on long jobs.
