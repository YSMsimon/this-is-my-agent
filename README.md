[中文版](README_CN.md)

> ***Currently discounted. Expect bugs, incomplete features, and rough edges. Error handling and try/catch coverage will be improved over time.**

A fully async, multi-agent CLI assistant with a **custom adapter layer** for LLM providers — swap between local Ollama models, OpenAI, DeepSeek, and more by changing one line in `.env`.

## Demo

### Simple Mode
https://github.com/user-attachments/assets/32a61057-fc00-4fc3-ad41-3c9c4300f57b

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

All agents inherit from a shared `Agent` base class that handles the streaming LLM loop, tool execution, `Rich.Live` spinner/renderer, and depth limiting. Each subclass overrides only what it needs.

---

## Adapter Architecture

```
adapters/
├── __init__.py               # Adapter: unified entry point, routes by provider prefix
├── schema.py                 # Response: canonical output format for all providers
├── base_adapter.py           # Abstract interface all adapters implement
├── openai_compat_adapter.py  # All OpenAI-compatible providers (DeepSeek, OpenAI, OpenRouter, etc.)
├── ollama_adapter.py         # Ollama (OpenAI-compatible client + embed support)
├── anthropic_adapter.py      # Anthropic
└── gemini_adapter.py         # Google Gemini
```

DeepSeek, OpenAI, and any external provider (OpenRouter, Together AI, Baidu AI, etc.) all share one adapter — `OpenAICompatAdapter` — since they all speak the OpenAI API. The router in `__init__.py` just passes the right `api_key` and `base_url` per provider. Only Ollama (embedding support), Anthropic, and Gemini need their own adapter.

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
    │  │        read_file, write_file,    │
    │  │        edit_file, run_bash,      │
    │  │        grep, glob, ask_user,     │
    │  │        to_do                     │
    │  └──────────────────────────────────┘
    │
    ▼
Response (streamed, rendered as Markdown)
```

Single agent loop with full tool access and user profile context. Fast and suitable for most tasks.

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
├── main.py                  # Entry point (async REPL, banner, prompt_toolkit session)
├── requirements.txt
├── Docker-compose.yml       # PostgreSQL + pgvector
├── init.sql                 # DB schema (auto-run on first start)
├── .env.example
│
├── adapters/
│   ├── __init__.py          # Adapter: unified router by provider prefix
│   ├── schema.py            # Response dataclass (canonical output format)
│   ├── base_adapter.py      # Abstract base adapter interface
│   ├── openai_compat_adapter.py  # DeepSeek, OpenAI, OpenRouter, etc.
│   ├── ollama_adapter.py         # Ollama provider adapter (+ embeddings)
│   ├── anthropic_adapter.py      # Anthropic provider adapter
│   └── gemini_adapter.py         # Gemini provider adapter
│
├── agent/
│   ├── base.py              # Base Agent: Rich.Live streaming, tool dispatch, depth limit
│   ├── loop.py              # MainAgent: memory, profile, simple/deep routing, token summary
│   ├── planner.py           # PlannerAgent: structured task decomposition
│   ├── executor.py          # ExecutorAgent: executes one task with tools
│   ├── evaluator.py         # EvaluatorAgent: structured pass/fail evaluation
│   ├── compact.py           # Compactor: summarises conversation history
│   └── profile.py           # ProfileManager: background user profiling
│
├── cli/
│   ├── commands.py          # CLI command handler (/help, /model, /compact, etc.)
│   ├── completions.py       # prompt_toolkit SlashCompleter + FillBgProcessor
│   ├── renderer.py          # print_user_message (dark-bg submitted line)
│   ├── theme.py             # Shared Rich Console + named theme styles
│   └── diff.py              # Claude Code-style red/green diff renderer
│
├── common/
│   └── config.py            # Loads .env and prompt files
│
├── memory/
│   └── db.py                # asyncpg pool, history, knowledge, profiles
│
├── tools/
│   ├── manager.py           # Tool definitions, named tool sets, styled confirmations
│   ├── crawl.py             # web_search, fetch_text, fetch_html (PDF via pymupdf)
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
| MainAgent (`/simple`) | run_bash, read_file, write_file, edit_file, grep, glob, web_search, fetch_text, ask_user, to_do |
| ExecutorAgent (`/deep`) | run_bash, read_file, write_file, edit_file, grep, glob, web_search, fetch_text |
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
| `/model all <provider/model>` | Set all models (main + all sub-models) to the same value |
| `/apikey deepseek <key>` | Update DeepSeek API key — writes directly to `.env` |
| `/apikey ollama <key>` | Update Ollama API key — writes directly to `.env` |
| `/apikey external <key>` | Update external provider API key — writes directly to `.env` |

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

# ── External provider (OpenRouter, Together AI, Baidu AI, etc.) ───────────────
# EXTERNAL_BASE_URL=https://openrouter.ai/api/v1
# EXTERNAL_API_KEY=sk-...

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
| External | `external/model` | `external/meta-llama/llama-3.1-70b-instruct` |

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
| `EXTERNAL_BASE_URL` | Base URL for any OpenAI-compatible provider (e.g. OpenRouter, Together AI) |
| `EXTERNAL_API_KEY` | API key for the external provider |

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
