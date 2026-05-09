[中文版](README_CN.md)

> **This project is actively in development. Expect bugs, incomplete features, and rough edges. Error handling and try/catch coverage will be improved over time.**

A fully async, multi-agent CLI assistant powered by Ollama with persistent memory, semantic search, user profile tracking, tool use, and two conversation modes: **Simple** and **Deep**.

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
Response
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
    ▼  (asyncio.gather — all run in parallel)
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

Deep mode breaks complex requests into parallel tasks, self-evaluates results, and spawns targeted fix executors if issues are found — before synthesising a final answer.

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

---

## Prerequisites

Install these before anything else:

| Dependency | Why |
|---|---|
| [Python 3.10+](https://www.python.org/downloads/) | Runs the agent |
| [Node.js 18+](https://nodejs.org/) | Required to run the WeChat ACP bridge (`npx wechat-acp`) |
| [Ollama](https://ollama.com/download) | Serves the LLM and embedding models locally |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Runs the PostgreSQL + pgvector database |

> **Does `pip install ollama` replace installing Ollama?**
> No. The `ollama` Python package (installed via `requirements.txt`) is just an HTTP client SDK — it lets Python talk to the Ollama server. You still need the **Ollama application** installed and running on your machine to actually load and serve models.

---

## Setup

### 1. Clone and install Python dependencies

```bash
git clone https://github.com/YSMsimon/this-is-my-agent.git
cd this-is-my-agent
pip install -r requirements.txt
```

### 2. Pull models via Ollama

Make sure Ollama is running first (open the Ollama app or run `ollama serve`), then pull the embedding model:

```bash
ollama pull nomic-embed-text
```

**For your main model (`MODEL`) and other models:**

- If you are using a **cloud model** (model name ends in `:cloud`, e.g. `qwen3-coder-next:cloud`), Ollama streams it from the cloud — no pull needed.
- If you are using a **local model** (no `:cloud` suffix, e.g. `qwen2.5-coder:7b`), you must pull it first:

```bash
ollama pull qwen2.5-coder:7b
```

For `PROFILE_MODEL`, `COMPACT_MODEL`, `PLANNER_MODEL`, and `EVALUATOR_MODEL`, a lightweight model works well since these are structured extraction tasks:

```bash
ollama pull qwen2.5:0.5b     # fastest, minimal RAM
ollama pull llama3.2:1b      # slightly more capable, still very light
ollama pull gemma3:1b        # good balance of speed and accuracy
```

### 3. Start the database

```bash
docker compose up -d
```

This starts a PostgreSQL instance with the pgvector extension on **port 5433**. The `init.sql` file sets up the required tables automatically on first run.

### 4. Configure environment variables

```bash
cp .env.exmaple .env
```

Edit `.env`:

```env
BASE_URL=http://localhost:11434
MODEL=qwen3-coder-next:cloud
DATABASE_URL=postgresql://myuser:mypassword@localhost:5433/agent_memory
EMBEDDING_MODEL=nomic-embed-text
PROFILE_MODEL=gemma4:31b-cloud
COMPACT_MODEL=gemma4:31b-cloud
PLANNER_MODEL=gemma4:31b-cloud
EVALUATOR_MODEL=gemma4:31b-cloud
```

### 5. Run

```bash
python3 main.py
```

Type your messages at the `User>` prompt. Use `/exit` to quit.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BASE_URL` | Ollama base URL (e.g. `http://localhost:11434`) |
| `MODEL` | Main chat model |
| `EMBEDDING_MODEL` | Embedding model for RAG |
| `PROFILE_MODEL` | Model for background profile updates |
| `COMPACT_MODEL` | Model for history compaction |
| `PLANNER_MODEL` | Model for task planning (deep mode) |
| `EVALUATOR_MODEL` | Model for result evaluation (deep mode) |
| `DATABASE_URL` | PostgreSQL connection string |

---

## WeChat ACP

> **Known issue:** CLI commands (e.g. `/exit`, `/help`) do not currently work when sent through the WeChat ACP interface. Use the terminal REPL for commands.

Enable the WeChat ACP bridge so you can chat with your agent through WeChat:

**1. Edit `wechat-acp.config.json`** and replace the placeholder paths with your own:

```json
{
  "agent": "python3 /YOUR/ABSOLUTE/PATH/this-is-my-agent/acp_agent.py",
  "cwd": "/YOUR/ABSOLUTE/PATH/this-is-my-agent"
}
```

- On **Mac/Linux**: run `pwd` inside the project folder to get your absolute path
- On **Windows**: use `python` instead of `python3`, and forward slashes: `C:/Users/yourname/this-is-my-agent`
- `cwd` is required so Python can resolve the `agent/`, `memory/`, and `tools/` package imports correctly

**2. Start the ACP bridge:**

- **Mac/Linux:**
  ```bash
  ./start-wechat-acp.sh
  ```
- **Windows (PowerShell):**
  ```powershell
  .\start-wechat-acp.ps1
  ```

Node.js must be installed for `npx` to work.
