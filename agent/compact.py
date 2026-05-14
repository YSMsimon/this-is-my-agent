import asyncio
from adapters import Adapter
from common.config import config

# Target token budget per chunk sent to the compact model.
# Uses ~4 chars/token heuristic — no tokenizer dependency needed.
_CHARS_PER_TOKEN = 4
_CHUNK_TOKEN_LIMIT = 30_000  # safe for most models (leaves room for prompt overhead)
_CHUNK_CHAR_LIMIT = _CHUNK_TOKEN_LIMIT * _CHARS_PER_TOKEN


def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


class Compactor:
    def __init__(self, db, user_id: str, cfg: config, adapter: Adapter):
        self.db = db
        self.user_id = user_id
        self.cfg = cfg
        self.adapter = adapter

    def _format_message(self, m: dict) -> str:
        return f"[{m['role'].upper()}]: {m['content']}"

    def _split_into_chunks(self, messages: list) -> list[list]:
        chunks, current, current_chars = [], [], 0
        for m in messages:
            text = self._format_message(m)
            if current and current_chars + len(text) > _CHUNK_CHAR_LIMIT:
                chunks.append(current)
                current, current_chars = [], 0
            current.append(m)
            current_chars += len(text)
        if current:
            chunks.append(current)
        return chunks

    async def _compact_chunk(self, messages: list, extra_prompt: str = None) -> str:
        conversation = "\n".join(self._format_message(m) for m in messages)
        prompt = self.cfg.compact_prompt
        if extra_prompt:
            prompt += f"\n\nAdditional instructions: {extra_prompt}"
        prompt += f"\n\nCONVERSATION:\n{conversation}\n\nSUMMARY:"
        resp = await self.adapter.complete(
            model=self.cfg.compact_model,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return resp.content.strip()

    async def _merge_summaries(self, summaries: list[str]) -> str:
        combined = "\n\n---\n\n".join(
            f"[Part {i+1}]\n{s}" for i, s in enumerate(summaries)
        )
        prompt = f"{self.cfg.compact_merge_prompt}\n\nSUMMARIES:\n{combined}\n\nMERGED SUMMARY:"
        resp = await self.adapter.complete(
            model=self.cfg.compact_model,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return resp.content.strip()

    async def compact(self, extra_prompt: str = None) -> str:
        history = await self.db.get_all_history(self.user_id)
        if not history:
            return "No history to compact."

        chunks = self._split_into_chunks(history)
        total_tokens = _estimate_tokens(
            "\n".join(self._format_message(m) for m in history)
        )
        print(f"  ~{total_tokens:,} tokens across {len(chunks)} chunk(s)")

        if len(chunks) == 1:
            summary = await self._compact_chunk(chunks[0], extra_prompt)
        else:
            print(f"  Compacting {len(chunks)} chunks in parallel...")
            chunk_summaries = await asyncio.gather(
                *[self._compact_chunk(chunk, extra_prompt) for chunk in chunks]
            )
            print(f"  Merging {len(chunk_summaries)} summaries...")
            summary = await self._merge_summaries(list(chunk_summaries))

        await self.db.set_out_of_context(self.user_id)
        await self.db.add_message(
            self.user_id, 'assistant',
            f"[COMPACTED HISTORY]\n{summary}",
            in_context=True
        )

        return summary
