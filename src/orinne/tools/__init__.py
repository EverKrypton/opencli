"""Tools system for OPENCLI - inspired by opencode."""

import os
import re
import json
import shlex
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod
import fnmatch


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str = ""
    data: Any = None


class Tool(ABC):
    name: str
    description: str
    parameters: Dict[str, Any]
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass
    
    def to_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class BashTool(Tool):
    name = "bash"
    description = "Execute bash commands. Use for terminal operations like git, npm, docker, etc."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute"
            },
            "workdir": {
                "type": "string",
                "description": "Working directory (optional)"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 120000)"
            }
        },
        "required": ["command"]
    }
    
    def __init__(self, workdir: str = None):
        self.workdir = workdir or os.getcwd()
    
    async def execute(self, command: str, workdir: str = None, timeout: int = 120000) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir or self.workdir
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout / 1000
            )
            
            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")
            
            if proc.returncode != 0:
                return ToolResult(
                    success=False,
                    output=output,
                    error=error or f"Command exited with code {proc.returncode}"
                )
            
            return ToolResult(success=True, output=output, error=error)
            
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="", error=f"Command timed out after {timeout}ms")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ReadTool(Tool):
    name = "read"
    description = "Read a file from the filesystem. Returns content with line numbers."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file"
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start from (1-indexed)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read"
            }
        },
        "required": ["file_path"]
    }
    
    async def execute(self, file_path: str, offset: int = 1, limit: int = 2000) -> ToolResult:
        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(success=False, output="", error=f"File not found: {file_path}")
            
            if path.is_dir():
                entries = list(path.iterdir())
                output = "\n".join(f"{e.name}{'/' if e.is_dir() else ''}" for e in entries)
                return ToolResult(success=True, output=output)
            
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            start = max(0, offset - 1)
            end = min(total_lines, start + limit)
            
            result_lines = []
            for i in range(start, end):
                line_num = i + 1
                result_lines.append(f"{line_num}: {lines[i].rstrip()}")
            
            output = "\n".join(result_lines)
            if end < total_lines:
                output += f"\n... ({total_lines - end} more lines)"
            
            return ToolResult(success=True, output=output, data={"total_lines": total_lines})
            
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteTool(Tool):
    name = "write"
    description = "Write content to a file. Creates the file if it doesn't exist."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file"
            },
            "content": {
                "type": "string",
                "description": "Content to write"
            }
        },
        "required": ["file_path", "content"]
    }
    
    def __init__(self, permission_handler: Callable = None):
        self.permission_handler = permission_handler
    
    async def execute(self, file_path: str, content: str) -> ToolResult:
        try:
            path = Path(file_path)
            
            if self.permission_handler:
                allowed = await self.permission_handler("write", file_path)
                if not allowed:
                    return ToolResult(success=False, output="", error="Permission denied")
            
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            
            return ToolResult(success=True, output=f"Wrote {len(content)} bytes to {file_path}")
            
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class EditTool(Tool):
    name = "edit"
    description = "Edit a file by replacing specific text. More precise than write."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file"
            },
            "old_string": {
                "type": "string",
                "description": "Text to find and replace"
            },
            "new_string": {
                "type": "string",
                "description": "Text to replace with"
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: false)"
            }
        },
        "required": ["file_path", "old_string", "new_string"]
    }
    
    def __init__(self, permission_handler: Callable = None):
        self.permission_handler = permission_handler
    
    async def execute(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> ToolResult:
        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(success=False, output="", error=f"File not found: {file_path}")
            
            if self.permission_handler:
                allowed = await self.permission_handler("edit", file_path)
                if not allowed:
                    return ToolResult(success=False, output="", error="Permission denied")
            
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if old_string not in content:
                return ToolResult(success=False, output="", error="old_string not found in file")
            
            count = content.count(old_string)
            if count > 1 and not replace_all:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Found {count} occurrences. Use replace_all=true or provide more context."
                )
            
            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            return ToolResult(
                success=True,
                output=f"Replaced {count if replace_all else 1} occurrence(s) in {file_path}"
            )
            
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GlobTool(Tool):
    name = "glob"
    description = "Find files matching a pattern. Supports **/*.js style patterns."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern (e.g., '**/*.py', 'src/**/*.ts')"
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory)"
            }
        },
        "required": ["pattern"]
    }
    
    async def execute(self, pattern: str, path: str = ".") -> ToolResult:
        try:
            base = Path(path).resolve()
            matches = []
            
            for root, dirs, files in os.walk(base):
                for f in files:
                    full_path = Path(root) / f
                    rel_path = full_path.relative_to(base)
                    if fnmatch.fnmatch(str(rel_path), pattern) or fnmatch.fnmatch(f, pattern):
                        matches.append(str(full_path))
            
            matches.sort()
            output = "\n".join(matches) if matches else "No files found"
            
            return ToolResult(success=True, output=output, data={"count": len(matches)})
            
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GrepTool(Tool):
    name = "grep"
    description = "Search for a regex pattern in file contents."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for"
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in"
            },
            "include": {
                "type": "string",
                "description": "File pattern to include (e.g., '*.py')"
            }
        },
        "required": ["pattern"]
    }
    
    async def execute(self, pattern: str, path: str = ".", include: str = None) -> ToolResult:
        try:
            regex = re.compile(pattern, re.MULTILINE | re.IGNORECASE)
            base = Path(path).resolve()
            results = []
            
            files_to_search = []
            if base.is_file():
                files_to_search = [base]
            else:
                for root, dirs, files in os.walk(base):
                    for f in files:
                        if include and not fnmatch.fnmatch(f, include):
                            continue
                        files_to_search.append(Path(root) / f)
            
            for file_path in files_to_search:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(f"{file_path}:{i}: {line.rstrip()}")
                except:
                    continue
            
            output = "\n".join(results[:500])
            if len(results) > 500:
                output += f"\n... ({len(results) - 500} more results)"
            
            return ToolResult(success=True, output=output, data={"count": len(results)})
            
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WebFetchTool(Tool):
    name = "webfetch"
    description = "Fetch content from a URL."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch"
            },
            "format": {
                "type": "string",
                "enum": ["text", "markdown", "html"],
                "description": "Output format (default: markdown)"
            }
        },
        "required": ["url"]
    }
    
    async def execute(self, url: str, format: str = "markdown") -> ToolResult:
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
            
            content = response.text
            
            if format == "markdown":
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(content, "html.parser")
                    for script in soup(["script", "style"]):
                        script.decompose()
                    content = soup.get_text(separator="\n")
                    content = re.sub(r"\n{3,}", "\n\n", content)
                except:
                    pass
            
            return ToolResult(success=True, output=content[:50000])
            
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class TaskTool(Tool):
    name = "task"
    description = "Launch a sub-agent for complex tasks. Use for parallel work."
    parameters = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Short description of the task"
            },
            "prompt": {
                "type": "string",
                "description": "Detailed prompt for the agent"
            },
            "agent_type": {
                "type": "string",
                "enum": ["general", "explore"],
                "description": "Type of agent to use"
            }
        },
        "required": ["description", "prompt"]
    }
    
    def __init__(self, agent_executor: Callable = None):
        self.agent_executor = agent_executor
    
    async def execute(self, description: str, prompt: str, agent_type: str = "general") -> ToolResult:
        if self.agent_executor:
            try:
                result = await self.agent_executor(prompt, agent_type)
                return ToolResult(success=True, output=result)
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))
        
        return ToolResult(success=False, output="", error="Task executor not configured")


class ToolsRegistry:
    def __init__(self, workdir: str = None, permission_handler: Callable = None):
        self.workdir = workdir or os.getcwd()
        self.permission_handler = permission_handler
        self._tools: Dict[str, Tool] = {}
        self._register_defaults()
    
    def _register_defaults(self):
        self.register(BashTool(self.workdir))
        self.register(ReadTool())
        self.register(WriteTool(self.permission_handler))
        self.register(EditTool(self.permission_handler))
        self.register(GlobTool())
        self.register(GrepTool())
        self.register(WebFetchTool())
    
    def register(self, tool: Tool):
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)
    
    def all(self) -> List[Tool]:
        return list(self._tools.values())
    
    def get_schemas(self) -> List[Dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, **kwargs) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, output="", error=f"Unknown tool: {name}")
        return await tool.execute(**kwargs)
