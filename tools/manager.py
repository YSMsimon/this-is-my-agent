import asyncio
from aioconsole import ainput
from common.config import WORKDIR, config
from tools.todo import PlanItem, ToDoManager
from tools.skill_manager import SkillManager
from tools.crawl import fetch_text, web_search
from pathlib import Path

_skill_manager = SkillManager(Path(__file__).parent.parent / "skills")
_skill_manager.load_skills()


async def run_bash(command: str) -> str:
    if 'rm' in command or 'sudo' in command:
        while True:
            user_input = await ainput("Warning: Command contains 'rm' or 'sudo'. Are you sure you want to run this? (Y/N) ")
            if user_input.lower() == 'y':
                break
            else:
                return "Command not executed, cancelled by user."
    print(f"Running command: {command}")
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=WORKDIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        return 'Error: Timeout(120s)'
    return (stdout.decode() + stderr.decode()).strip() or "(no output)"


async def read_file(file_path: str) -> str:
    print(f"Reading file: {file_path}")
    try:
        return await asyncio.to_thread(_read_file_sync, file_path)
    except Exception as e:
        return f"Error reading file: {e}"


async def write_file(file_path: str, content: str) -> str:
    print(f"Writing file: {file_path}")
    try:
        await asyncio.to_thread(_write_file_sync, file_path, content)
    except Exception as e:
        return f"Error writing file: {e}"
    return f"File {file_path} written successfully."


async def edit_file(file_path: str, old: str, new: str) -> str:
    print(f"Editing file: {file_path}")
    try:
        await asyncio.to_thread(_edit_file_sync, file_path, old, new)
    except Exception as e:
        return f"Error editing file: {e}"
    return f"File {file_path} edited successfully."


def _read_file_sync(file_path: str) -> str:
    with open(file_path, "r") as f:
        return f.read()


def _write_file_sync(file_path: str, content: str):
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def _edit_file_sync(file_path: str, old: str, new: str):
    with open(file_path, "r") as f:
        content = f.read()
    content = content.replace(old, new)
    with open(file_path, "w") as f:
        f.write(content)


async def to_do(items: list[PlanItem]) -> str:
    manager = ToDoManager()
    return manager.to_do(items)


async def list_skills() -> str:
    items = _skill_manager.list_skills()
    return '\n'.join(items) if items else "No skills available."


async def preview_skill(name: str) -> str:
    return _skill_manager.preview_skill(name) or f"Skill '{name}' not found."


async def get_skill(name: str) -> str:
    return _skill_manager.get_skill(name) or f"Skill '{name}' not found."


async def grep(pattern: str, path: str, recursive: bool = True) -> str:
    import re as _re
    from pathlib import Path as _Path
    results = []
    target = _Path(path)
    files = target.rglob('*') if (recursive and target.is_dir()) else [target]
    for f in files:
        if not f.is_file():
            continue
        try:
            for i, line in enumerate(f.read_text(errors='ignore').splitlines(), 1):
                line = line.replace('\x00', '')
                if line and _re.search(pattern, line):
                    results.append(f"{f}:{i}: {line.strip()}")
        except Exception:
            continue
    return '\n'.join(results) if results else "No matches found."


async def glob(pattern: str, path: str = '.') -> str:
    print(f"Searching for files with pattern: {pattern} in path: {path}")
    from pathlib import Path
    try:
        root = Path(path).expanduser().resolve()
        matches = sorted(root.glob(pattern))
        return '\n'.join(str(m) for m in matches) if matches else "No files found."
    except Exception as e:
        return f"Error: {e}"


async def run_sub_agent(prompt: str) -> str:
    from agent.loop import Agent
    print("Running sub-agent")
    subagent = Agent(config(), tools=tools, is_subagent=True)
    return await subagent.run(prompt)


tools = [{
    "type": "function",
    "function": {
        "name": "run_bash",
        "description": "Run a bash command",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to run"
                }
            },
            "required": ["command"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the contents of a file",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to read"
                }
            },
            "required": ["file_path"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write content to a file",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file"
                }
            },
            "required": ["file_path", "content"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": "Edit the contents of a file",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to edit"
                },
                "old": {
                    "type": "string",
                    "description": "The text to replace"
                },
                "new": {
                    "type": "string",
                    "description": "The text to replace it with"
                }
            },
            "required": ["file_path", "old", "new"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "fetch_text",
        "description": "Fetch the visible plain text content of a webpage (HTML tags stripped)",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL to fetch"}
            },
            "required": ["url"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo and return a list of results with title, url, and snippet",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "max_results": {"type": "integer", "description": "Maximum number of results to return (default 5)"}
            },
            "required": ["query"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "list_skills",
        "description": "List all available skills with their descriptions",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
},
{
    "type": "function",
    "function": {
        "name": "preview_skill",
        "description": "Show a short preview (name, description, first few lines) of a skill",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The skill name (e.g. 'algorithmic-art')"}
            },
            "required": ["name"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "get_skill",
        "description": "Load the full SKILL.md instructions for a skill. Call this before attempting any skill-based task.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The skill name (e.g. 'algorithmic-art')"}
            },
            "required": ["name"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "grep",
        "description": "Search file contents by regex pattern and return matching lines with file path and line number",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "File or directory path to search"},
                "recursive": {"type": "boolean", "description": "Recursively search subdirectories (default true)"}
            },
            "required": ["pattern", "path"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "glob",
        "description": "Find files by glob pattern (e.g. **/*.py, src/**/*.ts). Returns matching file paths.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g. **/*.py or src/**/*.ts"},
                "path": {"type": "string", "description": "Root directory to search from (default: current directory)"}
            },
            "required": ["pattern"]
        }
    }
}]

all_tools = tools + [{
    "type": "function",
    "function": {
        "name": "run_sub_agent",
        "description": "Run a sub-agent with a given prompt",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt to run the sub-agent with"
                }
            },
            "required": ["prompt"]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "to_do",
        "description": "Update the to-do list",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "The list of to-do items, each with content, status, and optional parent",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The content of the to-do item"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "The status of the to-do item (pending, in_progress, completed)"
                            },
                            "parent": {
                                "type": "string",
                                "description": "The content of the parent to-do item, if this is a subtask"
                            }
                        }
                    }
                }
            },
            "required": ["items"]
        }
    }
},]

tool_handler = {
    'run_bash': run_bash,
    'read_file': read_file,
    'write_file': write_file,
    'edit_file': edit_file,
    'to_do': to_do,
    'list_skills': list_skills,
    'preview_skill': preview_skill,
    'get_skill': get_skill,
    'run_sub_agent': run_sub_agent,
    'fetch_text': fetch_text,
    'web_search': web_search,
    'grep': grep,
    'glob': glob
}
