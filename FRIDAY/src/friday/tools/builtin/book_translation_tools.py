"""TASK-FRD-057 — book-page translation tool.

Lets the agent translate one photographed book page: OCR the image
file, translate the text to Telugu through Inference, save the page
and return the Telugu translation. The photo entry point is the
Telegram gateway; this tool is the chat-side equivalent for a local
image path.
"""

from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool
from friday.workflows import book_translation


class BookPageTranslateTool(BaseTool):
    """Translate one photographed book page to Telugu."""

    name = "translate_book_page"
    description = (
        "Translate one photographed book page to Telugu: OCR the image file, "
        "translate the text through Inference, save the page and return the "
        "Telugu translation. Pass the local image path and the book name; "
        "the page number auto-increments per book unless page_no is given."
    )
    safety_level = SafetyLevel.SENSITIVE
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Local path to the photographed book page (jpg/png).",
            },
            "book": {
                "type": "string",
                "description": "Book name (used for the saved page and progress tracking).",
            },
            "page_no": {
                "type": "integer",
                "description": "Page number; defaults to the next page for the book.",
            },
        },
        "required": ["image_path"],
    }

    def execute(self, image_path: str = "", book: str = "unspecified", page_no: int | None = None, **kwargs: Any) -> ToolResult:
        if not (image_path or "").strip():
            return ToolResult(name=self.name, content="No image path provided.", is_error=True, safety_level=self.safety_level)
        result = book_translation.translate_page(
            image_path.strip(), book=book or "unspecified", page_no=page_no
        )
        if not result.get("ok"):
            return ToolResult(
                name=self.name,
                content=f"Could not translate that page: {result.get('error', 'unknown error')}",
                is_error=True,
                safety_level=self.safety_level,
            )
        return ToolResult(
            name=self.name,
            content=(
                f"Page {result['page']} of {result['book']} — Telugu translation:\n\n"
                f"{result['telugu']}"
            ),
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "book": result["book"],
                "page": result["page"],
                "provider": result.get("provider", "llm"),
                "saved_path": result.get("saved_path", ""),
            },
        )


__all__ = ["BookPageTranslateTool"]
