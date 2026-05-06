[English](README.md)

> **本项目正在积极开发中，预计会存在 Bug、功能不完整及粗糙的地方。错误处理与 try/catch 覆盖将逐步完善。**

一个运行在本地的 AI 智能体，具备持久化记忆、语义搜索、用户画像追踪、工具调用以及微信 ACP 集成 —— 全部通过 Ollama 在你自己的硬件上运行。

---

## 项目结构

```
custom-agent/
├── agent/              # 核心智能体逻辑
│   ├── loop.py         # 主循环（LLM 调用、工具执行、RAG 注入）
│   ├── profile.py      # 后台用户画像提取
│   └── compact.py      # 对话历史压缩
├── memory/             # 数据库层
│   └── db.py           # PostgreSQL + pgvector（消息、画像、知识库）
├── tools/              # 工具实现与注册
│   ├── manager.py      # 工具注册表（bash、文件、搜索、技能等）
│   ├── crawl.py        # 网页抓取与 DuckDuckGo 搜索
│   ├── skill_manager.py# 技能加载器
│   └── todo.py         # 会话内任务追踪
├── cli/                # 命令行入口
│   └── commands.py     # 斜杠命令（/help、/profile、/compact 等）
├── common/             # 共享配置
│   └── config.py       # 环境变量加载
├── skills/             # 技能定义（SKILL.md + 示例 + 脚本 + 模板）
├── main.py             # 启动终端交互的入口文件
├── acp_agent.py        # 微信 ACP 服务入口
├── init.sql            # 数据库表结构（Docker 首次启动时自动执行）
└── Docker-compose.yml
```

---

## 工作原理

- 对话内容以向量嵌入的形式存储在 PostgreSQL 中，支持语义记忆召回
- 后台画像提取器自动从对话中构建结构化的开发者画像
- 智能体可调用工具：执行终端命令、搜索网页、读写文件等
- 通过 ACP（智能体通信协议）接入微信，让你可以直接在微信中与智能体对话

---

## 前置依赖

在开始之前，请先安装以下依赖：

| 依赖 | 用途 |
|---|---|
| [Python 3.10+](https://www.python.org/downloads/) | 运行智能体 |
| [Node.js 18+](https://nodejs.org/) | 运行微信 ACP 桥接服务（`npx wechat-acp`） |
| [Ollama](https://ollama.com/download) | 在本地运行 LLM 和嵌入模型 |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | 运行 PostgreSQL + pgvector 数据库 |

> **`pip install ollama` 是否可以替代安装 Ollama 应用？**
> 不能。`ollama` Python 包（通过 `requirements.txt` 安装）只是一个 HTTP 客户端 SDK，负责让 Python 与 Ollama 服务通信。你仍然需要在本机安装并运行 **Ollama 应用**来加载和运行模型。类比来说，这就像安装了 `psycopg2` 数据库驱动，但并不代表你有了数据库，只是有了连接数据库的能力。

---

## 安装步骤

### 1. 克隆项目并安装 Python 依赖

```bash
git clone https://github.com/YSMsimon/this-is-my-agent.git
cd this-is-my-agent
pip install -r requirements.txt
```

### 2. 通过 Ollama 拉取模型

先确保 Ollama 正在运行（打开 Ollama 应用或执行 `ollama serve`），然后拉取嵌入模型：

```bash
ollama pull nomic-embed-text
```

**关于主模型（`MODEL`）和画像模型（`PROFILE_MODEL`）：**

- 如果你使用的是**云端模型**（模型名称以 `:cloud` 结尾，例如 `qwen3-coder-next:cloud`），Ollama 会从云端流式加载，**无需提前拉取**，直接在 `.env` 中填写模型名称即可运行。
- 如果你使用的是**本地模型**（名称中没有 `:cloud` 后缀，例如 `qwen2.5-coder:7b`），则必须先拉取：

```bash
ollama pull qwen2.5-coder:7b
```

**关于 `PROFILE_MODEL`**，建议使用轻量级本地模型以获得最佳性能 —— 画像提取只是简单的结构化 JSON 抽取，不需要大模型。推荐选项：

```bash
ollama pull qwen2.5:0.5b     # 最快，占用内存最少
ollama pull llama3.2:1b      # 稍强一些，仍然非常轻量
ollama pull gemma3:1b        # 速度与精度的良好平衡
```

> 为 `PROFILE_MODEL` 使用轻量级本地模型，可以让画像更新真正在后台无感运行，不与主模型争抢资源。

### 3. 启动数据库

```bash
docker compose up -d
```

这将在 **5433 端口**启动一个带有 pgvector 扩展的 PostgreSQL 实例。`init.sql` 文件会在首次运行时自动创建所需的数据库表。

> Windows 用户请使用 Docker Desktop，并在 PowerShell 或 CMD 中执行命令。Mac 用户需要在运行 `docker compose` 前先打开 Docker Desktop。

### 4. 配置环境变量

复制示例环境变量文件并填写你的配置：

```bash
cp .env.exmaple .env
```

编辑 `.env` 文件：

```env
BASE_URL = "http://localhost:11434"
MODEL = "qwen3-coder-next:cloud"
DATABASE_URL = "postgresql://myuser:mypassword@localhost:5433/agent_memory"
EMBEDDING_MODEL = "nomic-embed-text"
PROFILE_MODEL = "gemma4:31b-cloud"
COMPACT_MODEL = "gemma4:31b-cloud"
```

`PROFILE_MODEL` 用于后台画像提取，推荐使用较小较快的模型，因为这个任务只是结构化的 JSON 抽取。

---

## 运行智能体

### 终端（交互式命令行）

```bash
python3 main.py
```

在 `User>` 提示符后输入消息。输入 `/exit` 退出。

### 微信 ACP

> **已知问题：** 通过微信 ACP 发送的 CLI 命令（如 `/exit`、`/help`）目前无法正常工作。这是已知限制，正在修复中 —— 目前请在终端中使用命令行功能。

按以下步骤启用微信 ACP 桥接：

**1. 编辑 `wechat-acp.config.json`**，将占位路径替换为你自己的实际路径：

```json
{
  "agent": "python3 /你的/绝对/路径/this-is-my-agent/acp_agent.py",
  "cwd": "/你的/绝对/路径/this-is-my-agent"
}
```

- **Mac/Linux**：在项目目录中执行 `pwd` 获取绝对路径
- **Windows**：将 `python3` 改为 `python`，并使用正斜杠，例如 `C:/Users/yourname/this-is-my-agent`
- `cwd` 是必须的 —— Python 需要通过它来解析 `agent/`、`memory/`、`tools/` 等包的导入路径

**2. 启动 ACP 桥接服务：**

- **Mac/Linux：**
  ```bash
  ./start-wechat-acp.sh
  ```
- **Windows（PowerShell）：**
  ```powershell
  .\start-wechat-acp.ps1
  ```

脚本会自动从 `wechat-acp.config.json` 中读取你的路径配置。

`npx` 需要安装 Node.js 才能使用。
