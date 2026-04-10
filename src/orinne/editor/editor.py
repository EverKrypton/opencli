"""Built-in code editor for OPENCLI."""

from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.formatters import TerminalFormatter
from pygments.util import ClassNotFound
import re


class ActionType(Enum):
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"


@dataclass
class EditorAction:
    type: ActionType
    position: Tuple[int, int]
    text: str
    old_text: str = ""


@dataclass
class Buffer:
    lines: List[str] = field(default_factory=list)
    filename: Optional[str] = None
    language: Optional[str] = None
    modified: bool = False
    cursor_line: int = 0
    cursor_col: int = 0
    scroll_offset: int = 0
    
    def __post_init__(self):
        if not self.lines:
            self.lines = [""]
    
    @classmethod
    def from_file(cls, filepath: str) -> "Buffer":
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.split("\n")
            
            try:
                lexer = guess_lexer_for_filename(filepath, content)
                language = lexer.name.lower()
            except ClassNotFound:
                language = None
            
            return cls(
                lines=lines,
                filename=filepath,
                language=language,
            )
        except FileNotFoundError:
            return cls(filename=filepath)
    
    def save(self, filepath: Optional[str] = None) -> bool:
        path = filepath or self.filename
        if not path:
            return False
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.lines))
            self.filename = path
            self.modified = False
            return True
        except IOError:
            return False
    
    @property
    def content(self) -> str:
        return "\n".join(self.lines)
    
    @property
    def line_count(self) -> int:
        return len(self.lines)
    
    def get_line(self, line_num: int) -> str:
        if 0 <= line_num < len(self.lines):
            return self.lines[line_num]
        return ""
    
    def insert_char(self, char: str, line: int, col: int) -> None:
        if line < 0 or line >= len(self.lines):
            return
        
        current_line = self.lines[line]
        if col < 0:
            col = 0
        elif col > len(current_line):
            col = len(current_line)
        
        self.lines[line] = current_line[:col] + char + current_line[col:]
        self.modified = True
    
    def insert_text(self, text: str, line: int, col: int) -> None:
        if not text:
            return
        
        lines_to_insert = text.split("\n")
        
        if len(lines_to_insert) == 1:
            self.insert_char(text, line, col)
            return
        
        current_line = self.lines[line] if line < len(self.lines) else ""
        first_part = current_line[:col]
        last_part = current_line[col:] if line < len(self.lines) else ""
        
        self.lines[line] = first_part + lines_to_insert[0]
        
        for i, insert_line in enumerate(lines_to_insert[1:-1], 1):
            self.lines.insert(line + i, insert_line)
        
        if len(lines_to_insert) > 1:
            self.lines.insert(line + len(lines_to_insert) - 1, lines_to_insert[-1] + last_part)
        
        self.modified = True
    
    def delete_char(self, line: int, col: int) -> str:
        if line < 0 or line >= len(self.lines):
            return ""
        
        current_line = self.lines[line]
        
        if col > 0:
            deleted = current_line[col - 1]
            self.lines[line] = current_line[:col - 1] + current_line[col:]
            self.modified = True
            return deleted
        elif line > 0:
            deleted = "\n"
            prev_line = self.lines[line - 1]
            self.lines[line - 1] = prev_line + current_line
            del self.lines[line]
            self.modified = True
            return deleted
        
        return ""
    
    def delete_line(self, line: int) -> str:
        if line < 0 or line >= len(self.lines):
            return ""
        
        deleted = self.lines[line]
        
        if len(self.lines) == 1:
            self.lines[0] = ""
        else:
            del self.lines[line]
        
        self.modified = True
        return deleted
    
    def insert_line(self, line: int, text: str = "") -> None:
        if line < 0:
            line = 0
        elif line > len(self.lines):
            line = len(self.lines)
        
        self.lines.insert(line, text)
        self.modified = True
    
    def get_word_at(self, line: int, col: int) -> Tuple[str, int, int]:
        if line < 0 or line >= len(self.lines):
            return "", 0, 0
        
        text = self.lines[line]
        if not text or col < 0 or col > len(text):
            return "", 0, 0
        
        start = col
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            start -= 1
        
        end = col
        while end < len(text) and (text[end].isalnum() or text[end] == "_"):
            end += 1
        
        return text[start:end], start, end
    
    def search(self, query: str, case_sensitive: bool = False) -> List[Tuple[int, int]]:
        results = []
        
        if not query:
            return results
        
        flags = 0 if case_sensitive else re.IGNORECASE
        
        for i, line in enumerate(self.lines):
            for match in re.finditer(re.escape(query), line, flags):
                results.append((i, match.start()))
        
        return results
    
    def replace_all(self, old: str, new: str, case_sensitive: bool = False) -> int:
        if not old:
            return 0
        
        count = 0
        flags = 0 if case_sensitive else re.IGNORECASE
        
        for i, line in enumerate(self.lines):
            new_line, n = re.subn(re.escape(old), new, line, flags=flags)
            if n > 0:
                self.lines[i] = new_line
                count += n
                self.modified = True
        
        return count


class Editor:
    def __init__(self, tab_size: int = 4, auto_indent: bool = True):
        self.tab_size = tab_size
        self.auto_indent = auto_indent
        self.buffers: List[Buffer] = []
        self.active_buffer: Optional[Buffer] = None
        self.undo_stack: List[EditorAction] = []
        self.redo_stack: List[EditorAction] = []
    
    def new_buffer(self, filename: Optional[str] = None) -> Buffer:
        buffer = Buffer(filename=filename)
        self.buffers.append(buffer)
        self.active_buffer = buffer
        return buffer
    
    def open_file(self, filepath: str) -> Buffer:
        buffer = Buffer.from_file(filepath)
        self.buffers.append(buffer)
        self.active_buffer = buffer
        return buffer
    
    def close_buffer(self, buffer: Optional[Buffer] = None) -> None:
        target = buffer or self.active_buffer
        if target and target in self.buffers:
            self.buffers.remove(target)
            if self.active_buffer == target:
                self.active_buffer = self.buffers[0] if self.buffers else None
    
    def switch_buffer(self, index: int) -> Optional[Buffer]:
        if 0 <= index < len(self.buffers):
            self.active_buffer = self.buffers[index]
        return self.active_buffer
    
    def highlight_line(self, line: str, language: Optional[str] = None) -> str:
        if not language:
            return line
        
        try:
            lexer = get_lexer_by_name(language)
            return highlight(line, lexer, TerminalFormatter()).rstrip()
        except ClassNotFound:
            return line
    
    def auto_indent_line(self, prev_line: str) -> str:
        if not self.auto_indent:
            return ""
        
        indent = ""
        for char in prev_line:
            if char in (" ", "\t"):
                indent += char
            else:
                break
        
        if prev_line.rstrip().endswith((":")):
            indent += " " * self.tab_size
        
        return indent
