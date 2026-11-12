"""
Unit tests for LLMResponseParser (code block & artifact extraction).
"""

from app.agents.parser import LLMResponseParser


def test_parse_markdown_header_style():
    response = """
Here is the implementation of the auth service:

### File: app/auth/service.py
```python
def authenticate(user: str, token: str) -> bool:
    return token == "secret"
```

And the configuration:

### File: config/auth.json
```json
{
    "enabled": true
}
```
"""
    files = LLMResponseParser.extract_files(response)
    assert len(files) == 2
    assert files[0].relative_path == "app/auth/service.py"
    assert "authenticate(user: str" in files[0].content
    assert files[0].language == "python"

    assert files[1].relative_path == "config/auth.json"
    assert '"enabled": true' in files[1].content


def test_parse_code_block_info_string():
    response = """
```python:src/models/user.py
class User:
    id: int
    name: str
```
"""
    files = LLMResponseParser.extract_files(response)
    assert len(files) == 1
    assert files[0].relative_path == "src/models/user.py"
    assert "class User:" in files[0].content


def test_parse_xml_file_tags():
    response = """
<file path="templates/index.html">
<!DOCTYPE html>
<html>
<body><h1>FORGE</h1></body>
</html>
</file>
"""
    files = LLMResponseParser.extract_files(response)
    assert len(files) == 1
    assert files[0].relative_path == "templates/index.html"
    assert "<h1>FORGE</h1>" in files[0].content


def test_parse_fallback_default_filename():
    response = """
```python
def main():
    print("Direct fallback")
```
"""
    files = LLMResponseParser.extract_files(response, default_filename="main.py")
    assert len(files) == 1
    assert files[0].relative_path == "main.py"
    assert 'print("Direct fallback")' in files[0].content


def test_parse_empty_or_no_code():
    assert LLMResponseParser.extract_files("") == []
    assert LLMResponseParser.extract_files("Just plain text with no code blocks.") == []


def test_generated_test_prose_is_not_python_source():
    assert LLMResponseParser.extract_files("Here is an exhaustive, professional test suite.", default_filename="test_main.py") == []


def test_generated_test_markdown_is_unwrapped_and_syntax_checked():
    text = "Here are the tests.\n```python\ndef test_csv():\n    assert 1 == 1\n```\n"
    files = LLMResponseParser.extract_files(text, default_filename="test_main.py")
    assert len(files) == 1
    assert files[0].content.startswith("def test_csv")
    assert "Here are" not in files[0].content


def test_already_unwrapped_python_is_accepted_but_broken_fenced_code_is_not():
    assert len(LLMResponseParser.extract_files("def test_csv():\n    assert 1 == 1", default_filename="test_main.py")) == 1
    assert LLMResponseParser.extract_files("```python\ndef invalid(\n```", default_filename="test_main.py") == []
