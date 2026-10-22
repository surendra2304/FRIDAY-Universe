"""
LLM Response and Code Block Parser for Project FORGE.
Extracts structured file paths, source code, and artifacts from markdown-formatted LLM responses.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger("agents.parser")


class ExtractedFile(BaseModel):
    """Represents a source file or artifact extracted from an LLM response."""

    relative_path: str = Field(
        ..., description="Target relative file path within workspace project root"
    )
    content: str = Field(..., description="Complete text content of the file")
    language: str | None = Field(default=None, description="Syntax highlighting language tag")


class LLMResponseParser:
    """
    Parses LLM markdown responses to extract target files and source code blocks.
    Supports markdown headers, code block info strings, XML tags, and fallback patterns.
    """

    @classmethod
    def extract_files(
        cls,
        response_text: str,
        default_filename: str | None = None,
    ) -> list[ExtractedFile]:
        """
        Parse response text and extract all delimited files and code blocks.
        """
        if not response_text or not response_text.strip():
            return []

        # Normalize unicode hyphens and dashes (e.g. \u2011, \u2013, \u2014) to standard ASCII '-'
        text = response_text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
        text = (
            text.replace("\u2018", "'")
            .replace("\u2019", "'")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
        )
        text = text.strip()
        extracted: list[ExtractedFile] = []
        seen_paths: set[str] = set()

        def _normalize_path(raw_path: str) -> str:
            # Strip backticks, quotes, extra spaces, and leading slashes
            p = raw_path.strip("`'\" \t\r\n").replace("\\", "/")
            while p.startswith("/"):
                p = p[1:]
            return p

        def _is_valid_file(file_path: str, content: str) -> bool:
            if not file_path or not content or not content.strip():
                return False
            lower_path = file_path.lower()
            if lower_path in [
                "path/to/file.py",
                "path/to/file.ext",
                "path/to/file.js",
                "relative/path/to/file.py",
                "relative/path/to/file.ext",
                "relative/path/to/file.js",
                "path/to/component.js",
                "path/to/component.tsx",
            ] or lower_path.startswith(("path/to/", "relative/path/to/")):
                return False

            stripped_content = content.strip()
            if stripped_content.lower() in [
                "<code>",
                "<complete code>",
                "<complete source code>",
                "<test code>",
                "<fixed code>",
                "<architecture spec>",
                "<language>",
                "...",
            ]:
                return False
            return not bool(re.match(r"^<[a-zA-Z0-9_\s-]+>$", stripped_content))

        # 1. XML Style: <file path="relative/path/to/file.ext">...</file>
        xml_matches = re.finditer(
            r'<file\s+(?:path|name|filename)=["\']([^"\']+)["\']\s*>\s*([\s\S]*?)\s*</file>',
            text,
            re.IGNORECASE,
        )
        for m in xml_matches:
            file_path = _normalize_path(m.group(1))
            file_content = m.group(2)
            # If content is wrapped in a markdown code fence inside the XML, unwrap it
            fence_match = re.search(
                r"^```[a-zA-Z0-9_-]*\s*\n([\s\S]*?)\n```$", file_content.strip()
            )
            if fence_match:
                file_content = fence_match.group(1)

            if _is_valid_file(file_path, file_content) and file_path not in seen_paths:
                extracted.append(ExtractedFile(relative_path=file_path, content=file_content))
                seen_paths.add(file_path)

        # NOTE: do NOT return early here. An XML-only match used to short-circuit
        # the whole function, silently dropping every "### File:" markdown block
        # in a mixed response. All patterns now accumulate and de-duplicate by
        # normalized path.

        # 2. Markdown File Header Pattern:
        # e.g., "### File: src/main.py\n```python\n...\n```"
        # or "**File:** `src/main.py`\n```python\n...\n```"
        # or "File: src/main.py\n```python\n...\n```"
        header_pattern = re.compile(
            # The trailing (?:\*{1,2}|_{1,2})? consumes the closing emphasis of
            # "**File:**" / "__File:__". Without it the bold form never matched.
            r"(?:#{1,6}\s+|(?:\*{1,2}|_{1,2})?File(?:\*{1,2}|_{1,2})?:\s*(?:\*{1,2}|_{1,2})?\s*|Target File:\s*)"
            r"[`\"']?([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9_\-]+)[`\"']?"
            r"(?:[^\n]*\n+)\s*"
            r"```([a-zA-Z0-9_\-#+]*)\s*\n"
            r"([\s\S]*?)\n```",
            re.IGNORECASE,
        )
        for m in header_pattern.finditer(text):
            file_path = _normalize_path(m.group(1))
            lang = m.group(2).strip() or None
            file_content = m.group(3)

            if _is_valid_file(file_path, file_content) and file_path not in seen_paths:
                extracted.append(
                    ExtractedFile(relative_path=file_path, content=file_content, language=lang)
                )
                seen_paths.add(file_path)

        # 3. Code Block Info String Pattern:
        # e.g., ```python:src/main.py ... ```
        # or ```python filepath=src/main.py ... ```
        # or ```python filename="src/main.py" ... ```
        info_pattern = re.compile(
            r"```([a-zA-Z0-9_\-#+]*)(?::|\s+(?:filepath|filename|file)=[\"']?)([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9_\-]+)[\"']?\s*\n"
            r"([\s\S]*?)\n```",
            re.IGNORECASE,
        )
        for m in info_pattern.finditer(text):
            lang = m.group(1).strip() or None
            file_path = _normalize_path(m.group(2))
            file_content = m.group(3)

            if _is_valid_file(file_path, file_content) and file_path not in seen_paths:
                extracted.append(
                    ExtractedFile(relative_path=file_path, content=file_content, language=lang)
                )
                seen_paths.add(file_path)

        # 4. Fallback: only when nothing structured was found at all.
        if not extracted and default_filename:
            generic_code_blocks = re.findall(
                r"```([a-zA-Z0-9_\-#+]*)\s*\n([\s\S]*?)\n```",
                text,
            )
            if generic_code_blocks:
                # Filter valid code blocks
                valid_blocks = [
                    (lang, block)
                    for lang, block in generic_code_blocks
                    if _is_valid_file(default_filename, block)
                ]
                if valid_blocks:
                    largest_lang, largest_block = max(valid_blocks, key=lambda b: len(b[1]))
                    norm_default = _normalize_path(default_filename)
                    if (
                        _is_valid_file(norm_default, largest_block)
                        and norm_default not in seen_paths
                    ):
                        extracted.append(
                            ExtractedFile(
                                relative_path=norm_default,
                                content=largest_block,
                                language=largest_lang or None,
                            )
                        )

        return extracted
