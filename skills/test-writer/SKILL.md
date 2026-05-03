---
name: test-writer
description: Write unit tests, integration tests, and test fixtures for any function, class, module, or API endpoint. Use this skill whenever the user wants to write tests, increase test coverage, test edge cases, set up pytest fixtures, mock external dependencies, test database operations, test an API endpoint, or debug a failing test. Trigger on phrases like "write tests for", "add unit tests", "test this function", "how do I test", "mock this", "pytest", "test coverage", "failing test", or "fixture".
---

# Test Writer

Write tests that actually catch bugs — not just tests that make coverage numbers go up. A test suite is only valuable if it fails when something breaks and passes when it doesn't.

---

## Core principles

**Test behaviour, not implementation.** Tests verify what code does, not how it does it. Renaming a private variable should never break a test.

**Each test tests one thing.** A test that checks five behaviours is hard to diagnose when it fails. One assertion (or closely related assertions) per test.

**Arrange-Act-Assert.** Every test has three parts: set up state → call the thing → verify the result.

**Tests are documentation.** The test name and body should tell a reader what the code does in a given scenario.

---

## Naming

```python
# Pattern: test_<function>_<scenario>_<expected>
def test_get_user_by_email_returns_user_when_found():
def test_get_user_by_email_returns_none_when_missing():
def test_add_message_raises_on_empty_content():
def test_semantic_search_excludes_provided_ids():
```

---

## pytest patterns

### Basic test
```python
from myapp.utils import format_currency

def test_format_currency_formats_positive_number():
    result = format_currency(1234.5)
    assert result == "$1,234.50"

def test_format_currency_handles_zero():
    assert format_currency(0) == "$0.00"

def test_format_currency_handles_negative():
    assert format_currency(-50.5) == "-$50.50"
```

### Testing exceptions
```python
import pytest
from myapp.agent import Agent

def test_run_raises_value_error_on_empty_message():
    agent = Agent(cfg=mock_config())
    with pytest.raises(ValueError, match="message cannot be empty"):
        agent.run("")

def test_save_turn_raises_on_unknown_role():
    with pytest.raises(ValueError, match="invalid role"):
        agent._save_turn({"role": "unknown", "content": "hi"})
```

### Parametrize — avoid duplicated test bodies
```python
import pytest
from myapp.utils import slugify

@pytest.mark.parametrize("input,expected", [
    ("Hello World",     "hello-world"),
    ("  spaces  ",      "spaces"),
    ("already-slug",    "already-slug"),
    ("UPPER CASE",      "upper-case"),
    ("special@chars!",  "specialchars"),
    ("",                ""),
])
def test_slugify(input, expected):
    assert slugify(input) == expected
```

### Fixtures
```python
import pytest
import psycopg2
import os
from db import DB

@pytest.fixture(scope="session")
def pg_connection():
    """Single connection for the test session."""
    conn = psycopg2.connect(os.getenv("TEST_DATABASE_URL"))
    yield conn
    conn.close()

@pytest.fixture(autouse=True)
def rollback(pg_connection):
    """Roll back after every test so state never leaks between tests."""
    yield
    pg_connection.rollback()

@pytest.fixture
def db(pg_connection):
    return DB(pg_connection)

@pytest.fixture
def seeded_user(db):
    """A user that already exists — for tests that need pre-existing data."""
    db.add_user("test@example.com", name="Alice")
    return db.get_user_by_email("test@example.com")
```

---

## Testing database code (your project)

```python
import pytest
import os
import psycopg2
from db import DB

@pytest.fixture(scope="session")
def conn():
    c = psycopg2.connect(os.getenv("TEST_DATABASE_URL"))
    yield c
    c.close()

@pytest.fixture(autouse=True)
def rollback_after_test(conn):
    yield
    conn.rollback()

@pytest.fixture
def db(conn):
    return DB(conn)

# --- Tests ---

def test_add_message_stores_content(db):
    db.add_message("user1", "user", "hello world", embedding=None, tool_call_id=None)

    history, _ = db.get_recent_history("user1", limit=10)

    assert len(history) == 1
    assert history[0]["content"] == "hello world"
    assert history[0]["role"] == "user"

def test_get_recent_history_respects_limit(db):
    for i in range(15):
        db.add_message("user1", "user", f"message {i}", embedding=None, tool_call_id=None)

    history, _ = db.get_recent_history("user1", limit=5)

    assert len(history) == 5

def test_get_recent_history_isolates_by_user(db):
    db.add_message("user1", "user", "alice message", embedding=None, tool_call_id=None)
    db.add_message("user2", "user", "bob message",   embedding=None, tool_call_id=None)

    history, _ = db.get_recent_history("user1", limit=100)
    contents = [m["content"] for m in history]

    assert "alice message" in contents
    assert "bob message" not in contents

def test_update_user_profile_merges_fields(db):
    db.update_user_profile("user1", {"name": "Alice", "job": "developer"})
    db.update_user_profile("user1", {"job": "senior developer"})  # partial update

    profile = db.get_user_profile("user1")

    assert profile["name"] == "Alice"               # preserved
    assert profile["job"] == "senior developer"     # updated
```

---

## Mocking external dependencies

Mock at the point of use, not the point of definition.

```python
from unittest.mock import patch, MagicMock, call

# Mocking the Ollama client
def test_agent_run_calls_chat_with_system_prompt(mock_config):
    with patch("my_agent_loop.Client") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        # Mock stream response
        mock_chunk = MagicMock()
        mock_chunk.message.content = "Hello!"
        mock_chunk.message.tool_calls = None
        mock_client.chat.return_value = [mock_chunk]

        # Mock embeddings
        mock_client.embeddings.return_value.embedding = [0.1] * 768

        agent = Agent(cfg=mock_config, db=MagicMock())
        agent.run("hi")

        # Verify chat was called
        assert mock_client.chat.called
        call_kwargs = mock_client.chat.call_args[1]
        assert call_kwargs["model"] == mock_config.model
        # System prompt contains user profile
        system_msg = call_kwargs["messages"][0]
        assert system_msg["role"] == "system"

# Mocking web search
def test_web_search_returns_empty_on_no_results():
    with patch("crawl.DDGS") as MockDDGS:
        MockDDGS.return_value.__enter__.return_value.text.return_value = []

        from crawl import web_search
        result = web_search("xkq92jfkwq2")

        assert result == []
```

### Mock just one method on a real object
```python
from unittest.mock import patch

def test_save_turn_calls_add_message(real_db):
    with patch.object(real_db, "add_message") as mock_add:
        agent = Agent(cfg=mock_config, db=real_db)
        agent._save_turn({"role": "user", "content": "hello"})

        mock_add.assert_called_once_with(
            agent.user_id, "user", "hello",
            unittest.mock.ANY,   # embedding — we don't care about the value
            None                 # tool_call_id
        )
```

---

## Testing FastAPI endpoints
```python
from fastapi.testclient import TestClient
from myapp.main import app

client = TestClient(app)

def test_health_check_returns_200():
    response = client.get("/health")
    assert response.status_code == 200

def test_create_user_returns_201_with_id():
    response = client.post("/users", json={
        "email": "alice@example.com",
        "name": "Alice"
    })
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert body["email"] == "alice@example.com"

def test_create_user_rejects_invalid_email():
    response = client.post("/users", json={"email": "not-an-email", "name": "Bob"})
    assert response.status_code == 422

def test_create_user_rejects_duplicate_email():
    client.post("/users", json={"email": "dup@example.com", "name": "Alice"})
    response = client.post("/users", json={"email": "dup@example.com", "name": "Bob"})
    assert response.status_code == 409

def test_get_user_returns_404_for_unknown_id():
    response = client.get("/users/99999999")
    assert response.status_code == 404
```

---

## Testing threaded/async code

```python
import threading
import time

def test_update_profile_runs_in_background(agent, mocker):
    """Profile update should not block — it runs in a daemon thread."""
    update_started = threading.Event()
    update_finished = threading.Event()

    original = agent._update_profile

    def tracked_update(*args, **kwargs):
        update_started.set()
        original(*args, **kwargs)
        update_finished.set()

    with patch.object(agent, "_update_profile", side_effect=tracked_update):
        agent._save_turn({"role": "user", "content": "I am Alice"})
        agent._save_turn({"role": "assistant", "content": "Hello Alice!"})

        # The call returns immediately — update runs in background
        assert not update_finished.is_set()  # not done yet
        update_finished.wait(timeout=5)       # wait max 5s
        assert update_finished.is_set()       # eventually completed
```

---

## conftest.py — shared fixtures

```python
# tests/conftest.py
import pytest
import os
import psycopg2
from unittest.mock import MagicMock
from common.config import config
from db import DB

@pytest.fixture(scope="session")
def pg_connection():
    conn = psycopg2.connect(os.getenv("TEST_DATABASE_URL"))
    yield conn
    conn.close()

@pytest.fixture(autouse=True)
def rollback(pg_connection):
    yield
    pg_connection.rollback()

@pytest.fixture
def db(pg_connection):
    return DB(pg_connection)

@pytest.fixture
def mock_config():
    cfg = MagicMock(spec=config)
    cfg.model = "test-model"
    cfg.embedding_model = "nomic-embed-text"
    cfg.profile_model = "test-model"
    cfg.base_url = "http://localhost:11434"
    cfg.system_prompt = "You are a test agent. {user_profile}"
    return cfg
```

---

## Common issues and fixes

### Test passes alone but fails in suite
```python
# Problem: test depends on state from a previous test (no rollback)
# Fix: use autouse rollback fixture, or db.close()/reopen between tests

@pytest.fixture(autouse=True)
def rollback(conn):
    yield
    conn.rollback()
```

### Mock not taking effect
```python
# Problem: patching the wrong module path
with patch("smtplib.SMTP"):           # BAD: patching the library
with patch("myapp.email.smtplib.SMTP"):  # GOOD: patching where it's imported

# Rule: patch where the name is looked up, not where it's defined
```

### "fixture 'X' not found"
```bash
# conftest.py must be in the tests/ directory (or a parent)
# Run pytest from the project root, not inside tests/
pytest tests/
```

### Slow tests
```python
# Use scope="session" for expensive fixtures (DB connection)
@pytest.fixture(scope="session")
def db_connection(): ...

# Mock external calls (HTTP, LLM inference) — don't make real network calls in tests
```

---

## Running tests

```bash
pytest                              # all tests
pytest tests/test_db.py             # specific file
pytest tests/test_db.py::test_add_message_stores_content  # specific test
pytest -k "profile"                 # tests matching name pattern
pytest -v                           # verbose
pytest -x                           # stop on first failure
pytest --tb=short                   # shorter tracebacks
pytest -s                           # show print output
pytest --cov=. --cov-report=term-missing   # coverage report
```
