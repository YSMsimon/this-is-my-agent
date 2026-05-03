---
name: code-review
description: Perform a structured, thorough code review on a file, function, snippet, or entire module. Use this skill whenever the user asks to review code, check code quality, audit a function, look for bugs, find security issues, assess readability, or wants feedback on their implementation. Trigger even if the user phrases it casually like "what do you think of this?", "is this good?", or "any issues here?" when code is present.
---

# Code Review

Perform a multi-dimensional code review. Think like a senior engineer doing a pull request review: honest, specific, and constructive. The goal is actionable, prioritised feedback — not a list of nitpicks.

---

## Review dimensions

Work through all of these. Skip a dimension only if it genuinely doesn't apply.

### 1. Correctness
- Does the code do what it claims?
- Are edge cases handled: empty input, `None`/`null`, zero, negative, very large values?
- Are exceptions caught at the right level, or swallowed silently?
- Are there off-by-one errors, wrong loop boundaries, or logic that fails on boundary values?

```python
# Bug: swallowed exception — error is lost silently
try:
    self.db.update_user_profile(self.user_id, json.loads(text))
except json.JSONDecodeError:
    pass   # ← bad: you'll never know this failed

# Better: at minimum log it
except json.JSONDecodeError as e:
    print(f"[profile] JSON parse failed: {e}", file=sys.stderr)
```

### 2. Security
- Is user input validated before use?
- Is there SQL injection risk? (Always use parameterised queries — never f-strings in SQL)
- Is there command injection? (`subprocess.run(command, shell=True)` with user input is dangerous)
- Are secrets hardcoded or logged?
- Are file paths from user input validated (path traversal risk)?

```python
# DANGEROUS: command injection — user can pass "ls; rm -rf /"
def run_bash(command: str) -> str:
    result = subprocess.run(command, shell=True, ...)

# The existing guard helps, but "shell=True" with user input is always risky
# For internal tools this is acceptable; for externally-exposed APIs it isn't

# SQL injection — wrong:
cursor.execute(f"SELECT * FROM users WHERE email = '{email}'")

# SQL injection — right (parameterised):
cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
```

### 3. Readability & naming
- Are names self-explanatory? A reader should understand what `user_message` holds without reading the body.
- Are functions short enough to hold in your head? (rough guide: 30–40 lines max)
- Is there unnecessary complexity that could be simplified?
- Are there magic numbers or strings that should be named constants?

```python
# Unclear name
def _save_turn(self, new_messages: Dict):

# Clearer
def _save_turn(self, message: Dict):   # it's one message, not multiple

# Magic number
if depth > 10:    # what is 10? where does it come from?

# Named constant
MAX_TOOL_DEPTH = 10
if depth > MAX_TOOL_DEPTH:
```

### 4. Design & structure
- Does each function do one thing?
- Is there duplicated logic that should be extracted?
- Is the function's responsibility clear from its name?
- Are side effects obvious and expected?

```python
# _build_messages does too many things: fetches history, computes embeddings,
# semantic searches, AND saves to DB — hard to test, hard to change
def _build_messages(self, user_message: str) -> List[Dict]:
    history, recent_ids = self.db.get_recent_history(...)  # I/O
    embedding = self.get_embedding(user_message)           # I/O
    memories = self.db.semantic_search(...)                # I/O
    self._save_turn(...)                                   # side effect!
    ...

# Side effects inside "build" functions are surprising — consider separating
```

### 5. Performance
- Are there N+1 queries (querying in a loop)?
- Are expensive operations (I/O, embedding generation) batched where possible?
- Are there unbounded operations (no limit on results, no recursion depth cap)?

```python
# Unbounded recursion: _execute calls itself with no depth limit
def _execute(self, messages):
    ...
    return self._execute(messages)   # if tools keep firing, this stack-overflows

# Fix:
def _execute(self, messages, depth=0):
    if depth > MAX_TOOL_DEPTH:
        return messages
    ...
    return self._execute(messages, depth + 1)
```

### 6. Error handling
- Are exceptions too broad (`except Exception`)? Catching everything hides real bugs.
- Are error messages useful for debugging?
- Does the code recover gracefully, or does one error crash the whole session?

```python
# Too broad — masks ALL errors including programmer mistakes
try:
    result = tool_handler[name](**args)
except Exception:
    pass

# Better — specific, with logging
except KeyError:
    print(f"[tool] unknown tool: {name}", file=sys.stderr)
    result = f"Error: no tool named '{name}'"
except TypeError as e:
    print(f"[tool] wrong args for {name}: {e}", file=sys.stderr)
    result = f"Error: {e}"
```

### 7. Tests (if provided or context makes it relevant)
- Are happy path, error path, and edge cases covered?
- Do tests verify behaviour, or just that the code runs without crashing?
- Are tests brittle — will they break when implementation details change?

---

## Output format

Always structure the review using this template:

---

### Summary
One short paragraph: what the code does, overall quality impression, the single most important thing to address.

### Critical issues
Bugs, security vulnerabilities, data loss risks. Must be fixed before shipping.

**Format for each issue:**
- **[Label]** What the problem is.
  - *Why it matters:* concrete consequence if not fixed.
  - *Suggestion:* specific fix or direction.

If none: write "None."

### Warnings
Should be fixed soon but won't immediately cause failure: missing error handling, performance issues, confusing naming, missing edge cases.

Same format as critical issues.

### Minor notes
Small improvements: style, naming, comments. Kept brief.

### Positives
One or two things done genuinely well. Reinforces good patterns.

---

## Adapting scope

- **Single function:** go deep on all 7 dimensions
- **Full file:** focus on structure and design first, drill into the riskiest parts
- **Diff / PR:** review only what changed, but flag if changes interact badly with surrounding code
- **"Is this fine?" quick check:** lead with summary + critical only, offer to go deeper

## Tone

Be direct. "This function will panic on empty input" is better than "you might want to consider handling empty input." Explain *why* something is a problem. Prioritise — 3 critical issues is more useful than 15 medium-priority comments. If the code is good, say so.
