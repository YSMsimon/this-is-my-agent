[中文版](README_CN.md)

> **This project is actively in development. Expect bugs, incomplete features, and rough edges. Error handling and try/catch coverage will be improved over time.**

A local AI agent with persistent memory, semantic search, user profile tracking, tool use, and WeChat ACP integration — all running on your own hardware via Ollama.

---

## Project Structure

```
custom-agent/
├── agent/              # Core agent logic
│   ├── loop.py         # Main agent loop (LLM calls, tool execution, RAG injection)
│   ├── profile.py      # Background user profile extraction
│   └── compact.py      # Conversation history compaction
├── memory/             # Database layer
│   └── db.py           # PostgreSQL + pgvector (messages, profiles, knowledge base)
├── tools/              # Tool implementations and schemas
│   ├── manager.py      # Tool registry, bash/file/search/skill tools
│   ├── crawl.py        # Web fetch and DuckDuckGo search
│   ├── skill_manager.py# Skill loader
│   └── todo.py         # In-session task tracking
├── cli/                # CLI entry point
│   └── commands.py     # Slash commands (/help, /profile, /compact, etc.)
├── common/             # Shared config
│   └── config.py       # Environment variable loading
├── skills/             # Skill definitions (SKILL.md + examples + scripts + templates)
├── main.py             # Run this to start the terminal REPL
├── acp_agent.py        # WeChat ACP server entry point
├── init.sql            # Database schema (auto-run by Docker on first start)
└── Docker-compose.yml
```

---

## How it works

- Conversations are stored in PostgreSQL with vector embeddings for semantic memory recall
- A background profile extractor builds a structured developer profile from your conversations automatically
- The agent can use tools: run bash commands, search the web, read/write files, and more
- Connects to WeChat via ACP (Agent Communication Protocol) so you can chat with your agent through WeChat

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
> No. The `ollama` Python package (installed via `requirements.txt`) is just an HTTP client SDK — it lets Python talk to the Ollama server. You still need the **Ollama application** installed and running on your machine to actually load and serve models. Think of it like installing the `psycopg2` database driver — it doesn't give you a database, it just lets you connect to one.

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

**For your main model (`MODEL`) and profile model (`PROFILE_MODEL`):**

- If you are using a **cloud model** (model name ends in `:cloud`, e.g. `qwen3-coder-next:cloud`), Ollama streams it from the cloud — no pull needed, just set the name in `.env` and run.
- If you are using a **local model** (no `:cloud` suffix, e.g. `qwen2.5-coder:7b`), you must pull it first:

```bash
ollama pull qwen2.5-coder:7b
```

**For `PROFILE_MODEL`**, use a lightweight local model for best performance — profile extraction is simple structured JSON work that does not need a large model. Recommended options:

```bash
ollama pull qwen2.5:0.5b     # fastest, minimal RAM
ollama pull llama3.2:1b      # slightly more capable, still very light
ollama pull gemma3:1b        # good balance of speed and accuracy
```

> Using a lightweight local model for `PROFILE_MODEL` keeps profile updates truly non-blocking in the background without competing for resources with your main model.

### 3. Start the database

```bash
docker compose up -d
```

This starts a PostgreSQL instance with the pgvector extension on **port 5433**. The `init.sql` file sets up the required tables automatically on first run.

> On Windows, use Docker Desktop and run the command in PowerShell or CMD. On Mac, Docker Desktop must be open before running `docker compose`.

### 4. Configure environment variables

Copy the example env file and fill in your values:

```bash
cp .env.exmaple .env
```

Edit `.env`:

```env
BASE_URL = "http://localhost:11434"
MODEL = "qwen3-coder-next:cloud"
DATABASE_URL = "postgresql://myuser:mypassword@localhost:5433/agent_memory"
EMBEDDING_MODEL = "nomic-embed-text"
PROFILE_MODEL = "gemma4:31b-cloud"
COMPACT_MODEL = "gemma4:31b-cloud"
```

The `PROFILE_MODEL` is used for background profile extraction — a smaller/faster model works well here since it's just structured JSON extraction.

---

## Running the agent

### Terminal (REPL)

```bash
python3 main.py
```

Type your messages at the `User>` prompt. Use `/exit` to quit.

### WeChat ACP

> **Known issue:** CLI commands (e.g. `/exit`, `/help`) do not currently work when sent through the WeChat ACP interface. This is a known limitation being worked on — for now, use the terminal REPL for commands.

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

The scripts read your path from `wechat-acp.config.json` automatically.

Node.js must be installed for `npx` to work.
