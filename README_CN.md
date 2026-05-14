[English](README.md)

> **本项目正在积极开发中，预计会存在 Bug、功能不完整及粗糙的地方。错误处理与 try/catch 覆盖将逐步完善。**

一个完全基于异步的多智能体 CLI 助手，内置**自定义适配器层**用于对接各 LLM 提供商 —— 只需修改 `.env` 中的一行，即可在本地 Ollama 模型、DeepSeek、OpenAI 等之间自由切换。

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

## 适配器架构

```
adapters/
├── __init__.py          # Adapter：统一入口，按提供商前缀路由
├── schema.py            # Response：所有提供商的统一输出格式
├── base_adapter.py      # 所有适配器须实现的抽象接口
├── deepseek_adapter.py  # DeepSeek 适配器（兼容 OpenAI 客户端）
├── ollama_adapter.py    # Ollama 适配器（兼容 OpenAI 客户端 + 支持嵌入）
├── anthropic_adapter.py # Anthropic 适配器
└── gemini_adapter.py    # Google Gemini 适配器
```

模型字符串采用 `提供商/模型名` 格式。`Adapter` 类读取前缀、路由到对应的提供商适配器，并在调用 API 前自动去除前缀。所有适配器均返回统一的 `Response` 对象：

```python
class Response(BaseModel):
    content: str
    tool_calls: list[dict] = []
    reasoning: str = ''
    model: str = ''
    finish_reason: str = ''
```

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
    ▼
推理步骤（主智能体对计划进行思考）
  - 任务顺序是否合理？
  - 任务之间是否存在依赖关系？
  - 执行器需要注意哪些风险或约束？
    │
    ▼  （asyncio.gather —— 所有任务并行运行，携带推理结果作为上下文）
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

深度模式在规划与执行之间新增了**推理步骤**。规划器生成任务列表后，主智能体会先对整个计划进行思考 —— 检查任务顺序、依赖关系和潜在风险 —— 再启动各执行器。推理结果会作为上下文传递给每个执行器。该步骤的提示词位于 `prompts/reasoning.md`，可直接编辑以调整推理行为。

---

## 项目结构

```
.
├── main.py                  # 入口文件（异步交互式命令行）
├── requirements.txt
├── Docker-compose.yml       # PostgreSQL + pgvector
├── init.sql                 # 数据库表结构（首次启动时自动执行）
├── .env.example
│
├── adapters/
│   ├── __init__.py          # Adapter：按提供商前缀统一路由
│   ├── schema.py            # Response 数据类（统一输出格式）
│   ├── base_adapter.py      # 抽象适配器接口
│   ├── deepseek_adapter.py  # DeepSeek 适配器
│   ├── ollama_adapter.py    # Ollama 适配器（含嵌入支持）
│   ├── anthropic_adapter.py # Anthropic 适配器
│   └── gemini_adapter.py    # Gemini 适配器
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
| `/context-window <n\|off>` | 限制加载最近 N 条历史；`off` 取消限制 |
| `/model` | 显示当前所有模型配置 |
| `/model <提供商/模型名>` | 更改主模型（如 `/model deepseek/deepseek-chat`） |
| `/model <角色> <提供商/模型名>` | 更改子模型：`compact`、`planner`、`evaluator`、`profile` |
| `/apikey deepseek <密钥>` | 更新 DeepSeek API 密钥 — 直接写入 `.env` 文件 |
| `/apikey ollama <密钥>` | 更新 Ollama API 密钥 — 直接写入 `.env` 文件 |

**模型偏好**（`/model`）保存至数据库，下次启动时自动恢复。子模型（`compact`、`planner`、`evaluator`、`profile`）若未单独设置则默认使用主 `MODEL`，数据库中的值优先于 `.env`。

**API 密钥**（`/apikey`）直接写入 `.env` 文件，该文件始终是唯一来源。手动编辑 `.env` 与使用 `/apikey` 命令效果完全相同，不存在数据库副本与文件内容冲突的问题。

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
cp .env.example .env
```

编辑 `.env` 文件 —— 模型字符串采用 `提供商/模型名` 格式：

```env
# ── 模型 ─────────────────────────────────────────────────────────────────────
MODEL=deepseek/deepseek-chat
EMBEDDING_MODEL=ollama/nomic-embed-text
PROFILE_MODEL=deepseek/deepseek-chat
COMPACT_MODEL=deepseek/deepseek-chat
PLANNER_MODEL=deepseek/deepseek-chat
EVALUATOR_MODEL=deepseek/deepseek-chat

# ── 数据库 ───────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://myuser:mypassword@localhost:5433/agent_memory

# ── API 密钥（填写你使用的提供商）──────────────────────────────────────────────
DEEPSEEK_API_KEY=...
# OPENAI_API_KEY=sk-...

# ── Ollama（仅在非默认地址时需要）────────────────────────────────────────────
# OLLAMA_BASE_URL=http://localhost:11434/v1
```

### 4. 运行

```bash
python3 main.py
```

---

## 模型字符串格式

模型字符串采用 `提供商/模型名` 格式，适配器层读取前缀并路由到对应提供商，调用 API 前自动去除前缀。

| 提供商 | 格式 | 示例 |
|--------|------|------|
| Ollama | `ollama/模型名` | `ollama/llama3.2` |
| DeepSeek | `deepseek/模型名` | `deepseek/deepseek-chat` |
| OpenAI | `openai/模型名` | `openai/gpt-4o` |

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
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `OLLAMA_BASE_URL` | 自定义 Ollama 地址（默认：`http://localhost:11434/v1`） |
| `OLLAMA_API_KEY` | Ollama API 密钥（默认：`dummy`） |

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
