Summarize the following conversation into a compact but complete record. Preserve:
- All facts the user shared (name, background, projects, preferences, goals)
- Key decisions and outcomes reached
- Any unresolved questions or ongoing tasks
- Technical context needed to continue the conversation naturally

Write the summary as structured notes. Be thorough — this replaces the full conversation history.

---

GOOD example output:

User: Simon, building a personal AI agent in Python. Prefers async, uses DeepSeek + Ollama.
Project: CLI agent with RAG memory (pgvector), multi-agent deep mode (planner → executors → evaluator).
Decisions: Switched from litellm to custom adapters. Context window set to 100 messages.
In progress: Adding Anthropic adapter. Debating whether to store API keys in DB or .env (decided: .env only).
Unresolved: WeChat ACP integration not tested yet.

Why good: Dense, specific, preserves all actionable context. Someone reading this could continue the conversation without the original history.

---

BAD example output:

The user talked about their AI project and made some decisions about the code. They seem to be making good progress.

Why bad: No specifics preserved. Names, decisions, technical context all lost. Useless as a history replacement.
