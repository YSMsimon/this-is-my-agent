[English](README.md)

> **本项目正在积极开发中，预计会存在 Bug、功能不完整及粗糙的地方。错误处理与 try/catch 覆盖将逐步完善。**

一个完全基于异步的多智能体 CLI 助手，使用 **[litellm](https://github.com/BerriAI/litellm)** 作为 LLM 客户端 —— 只需修改 `.env` 中的一行，即可在本地 Ollama 模型、Gemini、OpenAI、Anthropic、DeepSeek 等之间自由切换。

---

## 智能体架构

```
                  Agent（base.py）
                       │
      ┌────────────────┼────────────────┐
      │                │                │
 MainAgent        PlannerAgent    ExecutorAgent
 (loop.py)        (planner.py)    (executor.py)
      │
 EvaluatorAgent
 (evaluator.py)
```

所有智能体均继承自共享的 `Agent` 基类，该基类负责处理流式 LLM 循环、工具调度、加载动画和深度限制。每个子类只需重写自己需要的部分。

---

## 运行模式

### `/simple` — 简单模式

```
用户输入
    │
    ▼
MainAgent
    │  ┌──────────────────────────────────────┐
    ├──► 工具：web_search, fetch_text,         │
    │  │      read_file, ask_user, to_do      │
    │  └──────────────────────────────────────┘
    │
    ▼
流式响应输出
```

单智能体循环，拥有完整工具访问权限，并注入 RAG 记忆与用户画像上下文。速度快，适合大多数日常任务。

---

### `/deep` — 深度模式

```
用户输入
    │
    ▼
PlannerAgent ──► [ 任务1, 任务2, 任务3, ... ]
    │
    ▼  （asyncio.gather —— 所有任务并行运行）
ExecutorAgent-1   ExecutorAgent-2   ExecutorAgent-N
    │                  │                  │
    └──────────────────┴──────────────────┘
                        │
                        ▼
                 EvaluatorAgent
                        │
              ┌─────────┴──────────┐
            通过                  不通过（最多 3 轮）
              │                    │
              ▼                    ▼
           综合整合        ExecutorAgent x M（并行修复问题）
              │                    │
              ▼                    ▼
           响应输出         EvaluatorAgent（重新评估）
```

深度模式将复杂请求分解为并行子任务，对结果进行自我评估，若发现问题则生成针对性的修复执行器 —— 最终综合出完整答案。

---

## 项目结构

```
.
├── main.py                  # 入口文件（异步交互式命令行）
├── requirements.txt
├── litellm_config.yml       # LiteLLM 代理配置（可选）
├── Docker-compose.yml       # PostgreSQL + pgvector
├── init.sql                 # 数据库表结构（首次启动时自动执行）
├── .env.example
│
├── agent/
│   ├── base.py              # 基类 Agent：流式循环、工具调度、钩子函数
│   ├── loop.py              # MainAgent：记忆、RAG、画像、模式路由
│   ├── planner.py           # PlannerAgent：结构化任务分解
│   ├── executor.py          # ExecutorAgent：携带工具执行单个任务
│   ├── evaluator.py         # EvaluatorAgent：结构化通过/失败评估
│   ├── compact.py           # Compactor：对话历史压缩摘要
│   └── profile.py           # ProfileManager：后台用户画像更新
│
├── cli/
│   └── commands.py          # CLI 命令处理器
│
├── common/
│   └── config.py            # 加载 .env 和提示词文件
│
├── memory/
│   └── db.py                # asyncpg 连接池、历史记录、知识库、画像
│
├── tools/
│   ├── manager.py           # 工具定义与命名工具集
│   ├── crawl.py             # web_search, fetch_text, fetch_html
│   ├── todo.py              # ToDoManager + to_do 工具
│   └── skill_manager.py     # 技能加载器
│
├── prompts/
│   ├── agent.md             # 主智能体系统提示词
│   ├── subagent.md          # 子智能体系统提示词
│   ├── planner.md           # 规划器指令
│   ├── executor.md          # 执行器指令
│   ├── evaluator.md         # 评估器指令
│   ├── compact.md           # 压缩指令
│   └── profile.md           # 画像更新指令
│
└── skills/                  # 技能定义（SKILL.md + 示例 + 模板）
```

---

## 各智能体可用工具

| 智能体 | 可用工具 |
|--------|---------|
| MainAgent（`/simple`） | web_search, fetch_text, read_file, ask_user, to_do |
| ExecutorAgent（`/deep`） | web_search, fetch_text, read_file, ask_user |
| PlannerAgent | 无 |
| EvaluatorAgent | 无 |

---

## CLI 命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示所有可用命令 |
| `/exit` | 退出智能体 |
| `/simple` | 切换到简单模式（单智能体，速度快） |
| `/deep` | 切换到深度模式（多智能体，更彻底） |
| `/profile` | 查看当前用户画像 |
| `/delete-profile` | 删除已保存的用户画像 |
| `/clear-history` | 清除所有对话历史 |
| `/compact` | 将对话历史压缩为摘要 |
| `/compact "关注 X"` | 带额外指令的压缩 |

---

## 前置依赖

| 依赖 | 用途 |
|---|---|
| [Python 3.10+](https://www.python.org/downloads/) | 运行智能体 |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | 运行 PostgreSQL + pgvector 数据库 |
| [Ollama](https://ollama.com/download) | 仅在使用本地模型时需要 |
| [Node.js 18+](https://nodejs.org/) | 仅在使用微信 ACP 时需要 |

---

## 安装步骤

### 1. 克隆项目并安装 Python 依赖

```bash
git clone https://github.com/YSMsimon/this-is-my-agent.git
cd this-is-my-agent
pip install -r requirements.txt
```

### 2. 启动数据库

```bash
docker compose up -d
```

这将在 **5433 端口**启动一个带有 pgvector 扩展的 PostgreSQL 实例。`init.sql` 会在首次运行时自动创建所需的数据库表。

### 3. 配置环境变量

```bash
cp .env.exmaple .env
```

编辑 `.env` 文件 —— 所有模型字符串使用 litellm 格式（`提供商/模型名`）：

```env
# ── 模型 ─────────────────────────────────────────────────────────────────────
MODEL=gemini/gemini-2.0-flash
EMBEDDING_MODEL=ollama/nomic-embed-text
PROFILE_MODEL=gemini/gemini-2.0-flash
COMPACT_MODEL=gemini/gemini-2.0-flash
PLANNER_MODEL=gemini/gemini-2.0-flash
EVALUATOR_MODEL=gemini/gemini-2.0-flash

# ── 数据库 ───────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://myuser:mypassword@localhost:5433/agent_memory

# ── API 密钥（填写你使用的提供商）──────────────────────────────────────────────
GEMINI_API_KEY=...
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# DEEPSEEK_API_KEY=...

# ── Ollama（仅在非默认地址时需要）────────────────────────────────────────────
# OLLAMA_API_BASE=http://localhost:11434
```

### 4. 运行

```bash
python3 main.py
```

---

## 模型字符串格式

智能体使用 litellm，通过修改前缀即可切换任意提供商：

| 提供商 | 格式 | 示例 |
|--------|------|------|
| Ollama（对话） | `ollama_chat/模型名` | `ollama_chat/llama3.2` |
| Ollama（嵌入） | `ollama/模型名` | `ollama/nomic-embed-text` |
| Google Gemini | `gemini/模型名` | `gemini/gemini-2.0-flash` |
| OpenAI | `openai/模型名` | `openai/gpt-4o` |
| Anthropic | `anthropic/模型名` | `anthropic/claude-opus-4-5` |
| DeepSeek | `deepseek/模型名` | `deepseek/deepseek-chat` |

---

## 环境变量说明

| 变量名 | 说明 |
|--------|------|
| `MODEL` | 主对话模型 |
| `EMBEDDING_MODEL` | 用于 RAG 的嵌入模型 |
| `PROFILE_MODEL` | 后台画像更新使用的模型 |
| `COMPACT_MODEL` | 历史压缩使用的模型 |
| `PLANNER_MODEL` | 任务规划使用的模型（深度模式） |
| `EVALUATOR_MODEL` | 结果评估使用的模型（深度模式） |
| `DATABASE_URL` | PostgreSQL 连接字符串 |
| `OLLAMA_API_BASE` | 自定义 Ollama 地址（默认：`http://localhost:11434`） |
| `GEMINI_API_KEY` | Google Gemini API 密钥 |
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |

---

## LiteLLM 代理（可选）

项目内置的 `litellm_config.yml` 可以启动一个本地 OpenAI 兼容代理服务器，将请求路由到任意后端。适用于需要从其他工具访问智能体的场景。

```bash
litellm --config litellm_config.yml --port 4000
```

启动后，任何兼容 OpenAI 的客户端都可以将请求发送到 `http://localhost:4000`，并使用配置文件中定义的模型别名（`main`、`gpt-4o`、`claude-opus`、`gemini-flash` 等）。

---

## 微信 ACP

> **已知问题：** 通过微信 ACP 发送的 CLI 命令（如 `/exit`、`/help`）目前无法正常工作。请在终端中使用命令行功能。

**1. 编辑 `wechat-acp.config.json`**，将占位路径替换为你的实际路径：

```json
{
  "agent": "python3 /你的/绝对/路径/this-is-my-agent/acp_agent.py",
  "cwd": "/你的/绝对/路径/this-is-my-agent"
}
```

**2. 启动 ACP 桥接服务：**

- **Mac/Linux：** `./start-wechat-acp.sh`
- **Windows（PowerShell）：** `.\start-wechat-acp.ps1`

`npx` 需要安装 Node.js 才能使用。
