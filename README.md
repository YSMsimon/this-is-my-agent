[中文版](README_CN.md)

> **This project is actively in development. Expect bugs, incomplete features, and rough edges. Error handling and try/catch coverage will be improved over time.**

A fully async, multi-agent CLI assistant with a **custom adapter layer** for LLM providers — swap between local Ollama models, OpenAI, DeepSeek, and more by changing one line in `.env`.

---

## Agent Architecture

```
                     Agent (base.py)
                          │
         ┌────────────────┼────────────────┐
         │                │                │
    MainAgent        PlannerAgent    ExecutorAgent
    (loop.py)        (planner.py)    (executor.py)
         │
    EvaluatorAgent
    (evaluator.py)
```

All agents inherit from a shared `Agent` base class that handles the streaming LLM loop, tool execution, spinner, and depth limiting. Each subclass overrides only what it needs.

---

## Adapter Architecture

```
adapters/
├── __init__.py          # Adapter: unified entry point, routes by provider prefix
├── schema.py            # Response: canonical output format for all providers
├── base_adapter.py      # Abstract interface all adapters implement
├── deepseek_adapter.py  # DeepSeek (OpenAI-compatible client)
├── ollama_adapter.py    # Ollama (OpenAI-compatible client + embed support)
├── anthropic_adapter.py # Anthropic
└── gemini_adapter.py    # Google Gemini
```

Model strings use a `provider/model` format. The `Adapter` class reads the prefix, routes to the right provider adapter, and strips the prefix before the API call. All adapters return the same `Response` object:

```python
class Response(BaseModel):
    content: str
    tool_calls: list[dict] = []
    reasoning: str = ''
    model: str = ''
    finish_reason: str = ''
```

---

## Modes

### `/simple` — Simple Mode

```
User Input
    │
    ▼
MainAgent
    │  ┌──────────────────────────────────┐
    ├──► Tools: web_search, fetch_text,   │
    │  │        read_file, ask_user, to_do│
    │  └──────────────────────────────────┘
    │
    ▼
Response (streamed)
```

Single agent loop with full tool access, RAG memory injection, and user profile context. Fast and suitable for most tasks.

---

### `/deep` — Deep Mode

```
User Input
    │
    ▼
PlannerAgent ──► [ task1, task2, task3, ... ]
    │
    ▼
ReasoningStep (main agent thinks through the plan)
  - Are tasks in the right order?
  - Dependencies between tasks?
  - Risks or constraints executors should know?
    │
    ▼  (asyncio.gather — all run in parallel, with reasoning as context)
ExecutorAgent-1   ExecutorAgent-2   ExecutorAgent-N
    │                  │                  │
    └──────────────────┴──────────────────┘
                        │
                        ▼
                 EvaluatorAgent
                        │
              ┌─────────┴──────────┐
            PASS                 FAIL (up to 3 rounds)
              │                    │
              ▼                    ▼
          Synthesize       ExecutorAgent x M (fix issues, parallel)
              │                    │
              ▼                    ▼
          Response          EvaluatorAgent (re-evaluate)
```

Deep mode adds a **reasoning step** between planning and execution. After the planner produces tasks, the main agent thinks through the plan — checking task order, dependencies, and risks — before executors start. This reasoning is passed to every executor as additional context. The prompt for this step lives in `prompts/reasoning.md` and can be edited to tune the behaviour.

---

## Project Structure

```
.
├── main.py                  # Entry point (async REPL)
├── requirements.txt
├── Docker-compose.yml       # PostgreSQL + pgvector
├── init.sql                 # DB schema (auto-run on first start)
├── .env.example
│
├── adapters/
│   ├── __init__.py          # Adapter: unified router by provider prefix
│   ├── schema.py            # Response dataclass (canonical output format)
│   ├── base_adapter.py      # Abstract base adapter interface
│   ├── deepseek_adapter.py  # DeepSeek provider adapter
│   ├── ollama_adapter.py    # Ollama provider adapter (+ embeddings)
│   ├── anthropic_adapter.py # Anthropic provider adapter
│   └── gemini_adapter.py    # Gemini provider adapter
│
├── agent/
│   ├── base.py              # Base Agent: streaming loop, tool dispatch, hooks
│   ├── loop.py              # MainAgent: memory, RAG, profile, simple/deep routing
│   ├── planner.py           # PlannerAgent: structured task decomposition
│   ├── executor.py          # ExecutorAgent: executes one task with tools
│   ├── evaluator.py         # EvaluatorAgent: structured pass/fail evaluation
│   ├── compact.py           # Compactor: summarises conversation history
│   └── profile.py           # ProfileManager: background user profiling
│
├── cli/
│   └── commands.py          # CLI command handler
│
├── common/
│   └── config.py            # Loads .env and prompt files
│
├── memory/
│   └── db.py                # asyncpg pool, history, knowledge, profiles
│
├── tools/
│   ├── manager.py           # Tool definitions and named tool sets
│   ├── crawl.py             # web_search, fetch_text, fetch_html
│   ├── todo.py              # ToDoManager + to_do tool
│   └── skill_manager.py     # Skills loader
│
├── prompts/
│   ├── agent.md             # Main agent system prompt
│   ├── subagent.md          # Subagent system prompt
│   ├── planner.md           # Planner instructions
│   ├── executor.md          # Executor instructions
│   ├── evaluator.md         # Evaluator instructions
│   ├── compact.md           # Compaction instructions
│   └── profile.md           # Profile update instructions
│
└── skills/                  # Skill definitions (SKILL.md + examples + templates)
```

---

## Tool Access per Agent

| Agent | Tools |
|-------|-------|
| MainAgent (`/simple`) | web_search, fetch_text, read_file, ask_user, to_do |
| ExecutorAgent (`/deep`) | web_search, fetch_text, read_file, ask_user |
| PlannerAgent | none |
| EvaluatorAgent | none |

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/exit` | Exit the agent |
| `/simple` | Switch to simple mode (single agent, fast) |
| `/deep` | Switch to deep mode (multi-agent, thorough) |
| `/profile` | View your current user profile |
| `/delete-profile` | Delete your saved user profile |
| `/clear-history` | Delete all conversation history |
| `/compact` | Summarise and compress conversation history |
| `/compact "focus on X"` | Compact with extra instructions |
| `/context-window <n\|off>` | Limit history to last N messages; `off` removes the limit |
| `/model` | Show all current model settings |
| `/model <provider/model>` | Change the main model (e.g. `/model deepseek/deepseek-chat`) |
| `/model <role> <provider/model>` | Change a sub-model: `compact`, `planner`, `evaluator`, `profile` |
| `/apikey deepseek <key>` | Update DeepSeek API key — writes directly to `.env` |
| `/apikey ollama <key>` | Update Ollama API key — writes directly to `.env` |

**Model preferences** (`/model`) are saved to the database and restored automatically on the next launch. Sub-models (`compact`, `planner`, `evaluator`, `profile`) default to `MODEL` if not set — database values override `.env`.

**API keys** (`/apikey`) are written directly to your `.env` file — the file is always the source of truth. Editing `.env` manually and using `/apikey` are equivalent; there is no separate DB copy that could conflict.

---

## Prerequisites

| Dependency | Why |
|---|---|
| [Python 3.10+](https://www.python.org/downloads/) | Runs the agent |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Runs the PostgreSQL + pgvector database |
| [Ollama](https://ollama.com/download) | Only needed if using local models |
| [Node.js 18+](https://nodejs.org/) | Only needed for WeChat ACP bridge |

---

## Setup

### 1. Clone and install Python dependencies

```bash
git clone https://github.com/YSMsimon/this-is-my-agent.git
cd this-is-my-agent
pip install -r requirements.txt
```

### 2. Start the database

```bash
docker compose up -d
```

This starts a PostgreSQL instance with the pgvector extension on **port 5433**. The `init.sql` file sets up the required tables automatically on first run.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` — model strings use `provider/model` format:

```env
# ── Models ───────────────────────────────────────────────────────────────────
MODEL=deepseek/deepseek-chat
EMBEDDING_MODEL=ollama/nomic-embed-text
PROFILE_MODEL=deepseek/deepseek-chat
COMPACT_MODEL=deepseek/deepseek-chat
PLANNER_MODEL=deepseek/deepseek-chat
EVALUATOR_MODEL=deepseek/deepseek-chat

# ── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://myuser:mypassword@localhost:5433/agent_memory

# ── API keys (fill in the provider(s) you use) ───────────────────────────────
DEEPSEEK_API_KEY=...
# OPENAI_API_KEY=sk-...

# ── Ollama (only if not on default localhost:11434) ───────────────────────────
# OLLAMA_BASE_URL=http://localhost:11434/v1
```

### 4. Run

```bash
python3 main.py
```

---

## Model String Format

Model strings follow a `provider/model` format. The adapter layer reads the prefix, routes to the correct provider, and strips it before the API call.

| Provider | Format | Example |
|----------|--------|---------|
| Ollama | `ollama/model` | `ollama/llama3.2` |
| DeepSeek | `deepseek/model` | `deepseek/deepseek-chat` |
| OpenAI | `openai/model` | `openai/gpt-4o` |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MODEL` | Main chat model |
| `EMBEDDING_MODEL` | Embedding model for RAG |
| `PROFILE_MODEL` | Model for background profile updates |
| `COMPACT_MODEL` | Model for history compaction |
| `PLANNER_MODEL` | Model for task planning (deep mode) |
| `EVALUATOR_MODEL` | Model for result evaluation (deep mode) |
| `DATABASE_URL` | PostgreSQL connection string |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `OLLAMA_BASE_URL` | Custom Ollama URL (default: `http://localhost:11434/v1`) |
| `OLLAMA_API_KEY` | Ollama API key (default: `dummy`) |

---

## WeChat ACP

> **Known issue:** CLI commands (e.g. `/exit`, `/help`) do not currently work when sent through the WeChat ACP interface. Use the terminal REPL for commands.

**1. Edit `wechat-acp.config.json`** and replace the placeholder paths with your own:

```json
{
  "agent": "python3 /YOUR/ABSOLUTE/PATH/this-is-my-agent/acp_agent.py",
  "cwd": "/YOUR/ABSOLUTE/PATH/this-is-my-agent"
}
```

**2. Start the ACP bridge:**

- **Mac/Linux:** `./start-wechat-acp.sh`
- **Windows (PowerShell):** `.\start-wechat-acp.ps1`

Node.js must be installed for `npx` to work.
