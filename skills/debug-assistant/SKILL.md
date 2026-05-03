---
name: debug-assistant
description: Systematically debug errors, exceptions, unexpected behaviour, and failing tests. Use this skill whenever the user shows an error message, stack trace, wrong output, or describes something that isn't working. Trigger on phrases like "I'm getting an error", "this isn't working", "why is this failing", "I don't understand this traceback", "help me debug", "getting a TypeError/ValueError/KeyError/AttributeError", or when any stack trace or error message is present in the conversation.
---

# Debug Assistant

Work through bugs systematically. The goal is to understand *why* the code is failing, not just silence the error. A fix that papers over a root cause creates bigger problems later.

---

## Debugging process

### Step 1: Read the full traceback — bottom to top

The last line is the error. The frames above show the call chain that led there.

```
Traceback (most recent call last):
  File "my_agent_loop.py", line 172, in <module>
    agent.run(user_input)
  File "my_agent_loop.py", line 118, in run
    messages = self._build_messages(user_message)
  File "my_agent_loop.py", line 49, in _build_messages
    self._save_turn({'role': 'user', 'content': user_message})
  File "my_agent_loop.py", line 108, in _save_turn
    def _save_turn(self, new_messages: Dict, assistance_content: str):
TypeError: Agent._save_turn() missing 1 required positional argument: 'assistance_content'
          ↑ This is the actual problem — read this line first
```

Find the last frame that points to *your* code (not a library). That's where to look.

### Step 2: Inspect state at the failure point

Add temporary prints to see what values are present at the line that failed:

```python
def _save_turn(self, new_messages):
    print(f"[DEBUG] _save_turn: role={new_messages.get('role')}, content={str(new_messages.get('content'))[:80]}")
    role = new_messages.get('role')
    ...
```

Or use `breakpoint()` to drop into the interactive debugger:
```python
breakpoint()   # execution pauses here, opens pdb
# pdb commands:
# p variable   — print a value
# pp obj       — pretty-print
# l            — show current source
# n            — next line (step over)
# s            — step into function
# c            — continue
# q            — quit
# where        — show full stack
```

### Step 3: Trace the root cause backwards

Ask: why does this variable have this value? Follow it backwards through the code:
- Where is this variable assigned?
- What conditions or paths lead to this value?
- Is it initialised in `__init__`? Is the class instance the right one?

### Step 4: Form a hypothesis, then verify before fixing

Write out: "I think X is happening because Y." Then add a print or assertion to prove it before writing any fix.

### Step 5: Apply the minimal fix

Change only what addresses the root cause. Resist the urge to "clean up" surrounding code at the same time — that creates two diffs in one and makes reviews harder.

---

## Common Python errors

### TypeError: missing argument
```python
# Error:
TypeError: Agent._save_turn() missing 1 required positional argument: 'assistance_content'

# Cause: function signature changed but call sites weren't updated
# Fix: update the call site, or make the parameter optional:
def _save_turn(self, new_messages: Dict, assistance_content: str = None):
```

### TypeError: 'NoneType' object is not subscriptable / has no attribute
```python
# Error:
AttributeError: 'NoneType' object has no attribute 'get'
TypeError: 'NoneType' object is not subscriptable

# Cause: variable is None when you expected a value
# Debug:
print(type(my_var), my_var)   # always print type AND value

# Where to look: where the variable is assigned — why didn't it get a value?
# Common culprits:
#   - dict.get("key") returns None when key is missing
#   - function returns None implicitly (missing return statement)
#   - DB query returned no rows
#   - ENV variable not set: os.getenv("MISSING") returns None
```

### KeyError
```python
# Error:
KeyError: 'embedding'

# Cause: key doesn't exist in the dict
# Debug:
print(my_dict.keys())   # what keys actually exist?

# Fix: use .get() with a default, or check first:
embedding = my_dict.get('embedding')
if 'embedding' in my_dict:
    ...
```

### AttributeError: object has no attribute
```python
# Error:
AttributeError: 'Agent' object has no attribute '_last_user_message'

# Cause: attribute used before it's set in __init__
# Fix: initialise it in __init__:
def __init__(self, ...):
    self._last_user_message = ''
```

### JSONDecodeError
```python
# Error:
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

# Cause: the string isn't valid JSON
# Debug: print the raw string before parsing
print(repr(text))   # repr shows hidden characters, newlines, etc.

# Common causes:
# - LLM returned markdown with ```json ... ``` — strip the fences first
# - Empty string — add a guard: if not text.strip(): return
# - Partial response — model was cut off mid-generation
```

### RecursionError
```python
# Error:
RecursionError: maximum recursion depth exceeded

# In your project: _execute() calls itself with tool results
# Cause: tool loop never terminates — agent keeps calling tools endlessly
# Fix: add a depth limit:
def _execute(self, messages, depth=0):
    if depth > 10:
        return messages + [{'role': 'assistant', 'content': 'Max tool depth reached.'}]
    ...
    return self._execute(messages, depth + 1)
```

### psycopg2.OperationalError: could not connect to server
```bash
# Cause 1: Docker not running
docker compose ps       # check status
docker compose up -d    # start it

# Cause 2: Wrong host in DATABASE_URL
# Inside docker-compose use service name:    postgresql://myuser:pw@db:5432/dbname
# From host machine use localhost:           postgresql://myuser:pw@localhost:5433/dbname

# Cause 3: DB not ready yet (healthcheck not passed)
docker compose logs db  # look for "database system is ready to accept connections"

# Cause 4: Wrong port — compose maps 5433 on host to 5432 in container
DATABASE_URL=postgresql://myuser:mypassword@localhost:5433/agent_memory  # from host
```

### psycopg2.errors.UndefinedTable
```bash
# Cause: init.sql didn't run, or ran before extension was created
docker compose down -v          # remove volumes (clears DB)
docker compose up -d            # re-runs init.sql on fresh DB
```

### ImportError / ModuleNotFoundError
```bash
# Cause 1: package not installed
pip install -r requirements.txt

# Cause 2: wrong virtual environment active
which python3                    # check which python you're using
pip list | grep ollama           # check if it's installed

# Cause 3: relative import issue
# In Python, `from common.config import config` requires running from project root
cd /Users/simon/Desktop/custom-agent
python3 my_agent_loop.py
```

### ollama._types.ResponseError: model not found
```bash
# Cause: model not pulled yet
ollama list                      # see what's available
ollama pull nomic-embed-text     # pull missing model
ollama pull qwen2.5:0.5b         # pull profile model
```

---

## Debugging your specific stack

### Agent loop — conversation not responding
```python
# Add stderr prints to trace execution
def _execute(self, messages):
    print(f"[_execute] messages count: {len(messages)}", file=sys.stderr)
    response = self.client.chat(...)
    for chunk in response:
        # already printing content to stderr — check if this is reached
        pass
    print(f"[_execute] full_content length: {len(full_content)}", file=sys.stderr)
```

### Profile not updating
```python
# In _update_profile, add debug print before the LLM call
def _update_profile(self, user_message, assistant_response):
    existing = self.db.get_user_profile(self.user_id)
    print(f"[profile] existing: {existing}", file=sys.stderr)
    print(f"[profile] user_msg: {user_message[:100]}", file=sys.stderr)
    ...
    # After parsing:
    print(f"[profile] parsed: {json.loads(text)}", file=sys.stderr)
```

### Tool not being called
```python
# Check the tool_calls in the response
for chunk in response:
    if chunk.message.tool_calls:
        print(f"[tool_calls] {chunk.message.tool_calls}", file=sys.stderr)
```

### Semantic search returning wrong results
```python
# Check embedding dimensions match
embedding = self.get_embedding("test query")
print(f"[embed] dims: {len(embedding)}")  # should match vector(N) in schema

# Check the query being run
# Add logging to db.semantic_search()
```

---

## Logging instead of print

For anything beyond temporary debugging, use `logging`:

```python
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

logger.debug("_save_turn called: role=%s", role)
logger.info("Profile updated for user %s", self.user_id)
logger.warning("JSON parse failed, retrying: %s", e)
logger.error("Tool handler missing for %s", name)
```

---

## Output format

**1. What the error means** — plain English, what kind of failure this is.

**2. Root cause** — the specific condition that caused it, with reference to the relevant line/function.

**3. Fix** — exact code change with before/after.

**4. How to verify** — the test or command to confirm it's fixed.

**5. Watch out for** — any related risk the fix might introduce, or a deeper structural issue worth noting.

If there's not enough information, ask for: the full traceback, the relevant function, and what input triggered the error.
