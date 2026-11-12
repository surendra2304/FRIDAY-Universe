"""Do not truncate real Python at Markdown examples inside its docstring."""
from types import SimpleNamespace
import pytest
from app.services.code_generation import extract_code, CodeGenerationService, CodeGenerationRequest
from app.providers.unified_manager import unified_provider_manager

SOURCE = '''"""CSV conversion utility.

Example input:
```csv
name,city
"Doe, Jane",Guntur
```

Call convert to read the CSV.
"""
import csv
import io

def convert(text):
    return list(csv.DictReader(io.StringIO(text)))
'''


def test_valid_unfenced_python_is_not_replaced_by_its_docstring_example():
    assert extract_code(SOURCE, 'python') == SOURCE.strip()


def test_outer_python_fence_survives_inner_docstring_fences():
    reply = 'Here is the module.\n```python\n' + SOURCE + '```\nDone.'
    assert extract_code(reply, 'python') == SOURCE.strip()


def test_first_complete_python_block_still_wins():
    assert extract_code('```python\nx = 1\n```\n```python\ny = 2\n```', 'python') == 'x = 1'


@pytest.mark.asyncio
async def test_generation_validates_complete_code_not_truncated_docstring(monkeypatch):
    async def provider(request):
        return SimpleNamespace(content='```python\n'+SOURCE+'```', degraded=False, status='success', token_usage={})
    monkeypatch.setattr(unified_provider_manager, 'execute', provider)
    result = await CodeGenerationService().generate_code(CodeGenerationRequest(filename='main.py'))
    assert result.generation_path == 'agent'
    assert result.code == SOURCE.strip()
