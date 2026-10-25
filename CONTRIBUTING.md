# Contributing to FRIDAY Universe

Thank you for your interest in contributing! FRIDAY Universe is a multi-agent intelligence platform with 9 agents across 3 layers (basic, advanced, deep).

## Getting Started

1. **Fork** the repository
2. **Clone** your fork:
   ```bash
   git clone https://github.com/your-username/FRIDAY-Universe.git
   cd FRIDAY-Universe
   ```
3. **Set up environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install fastapi uvicorn httpx pydantic pytest requests numpy scipy matplotlib pandas
   cp .env.example .env  # Fill in your API keys
   ```

## Development Setup

### Running Tests

```bash
# Run all real functional tests
bash scripts/run_all_real_tests.sh

# Run individual suites
python3 -m pytest tests/test_real_functional_engines.py -v
python3 -m pytest tests/test_real_deep_engines.py -v
python3 -m pytest tests/test_real_http_api.py -v
```

### Starting the API Server

```bash
export PYTHONPATH=FRIDAY/apps/core/src:Inference/app:Inference:Memora:Stratex:Forge/app/services:Sentinel/app/services:IntelX/intelx/services:Futuris/futuris/core:VyralX/app/services
python3 -m uvicorn friday_core.real_api_server:app --host 0.0.0.0 --port 8000
```

## Code Standards

### Python Style
- **Type hints**: All functions must have type hints
- **Docstrings**: All public functions and classes must have docstrings
- **Line length**: 120 characters maximum
- **Imports**: Standard library first, then third-party, then local

### Architecture Rules
- **Never hardcode credentials** — use `os.getenv()` or environment files
- **Every engine must have real logic** — no stubs, no mocks
- **Every engine must have tests** — add to the appropriate test suite
- **Use importlib for cross-agent loading** — avoid sys.path collisions

### Testing
- **All new engines must have functional tests**
- **Test the real behavior**, not just structure
- **HTTP API tests** should use real HTTP requests (skip if server not running)

## Adding a New Engine

1. Create the engine file in the appropriate agent directory:
   ```
   <Agent>/<path>/real_<layer>_<name>.py
   ```

2. Implement real functional logic with:
   - Dataclasses for data models
   - Real algorithms (not stubs)
   - State persistence where appropriate

3. Add tests to the appropriate test suite:
   ```python
   # tests/test_real_<layer>_engines.py
   def load_module(relpath, name):
       spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
       mod = importlib.util.module_from_spec(spec)
       sys.modules[name] = mod
       spec.loader.exec_module(mod)
       return mod

   class TestNewEngine:
       def test_engine(self):
           engine = NewEngine()
           result = engine.do_something()
           assert result is not None
   ```

4. If adding API endpoints, add to `real_api_server.py`

## Commit Messages

Use clear, descriptive commit messages:
```
feat: add real sentiment analysis engine to Stratex
fix: correct pattern recognition threshold from 0.05 to 0.03
test: add 5 HTTP API tests for deep security endpoints
docs: update README with new endpoint table
```

## Pull Requests

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/new-engine-name
   ```

2. **Commit your changes** with clear messages

3. **Push to your fork**:
   ```bash
   git push origin feature/new-engine-name
   ```

4. **Open a PR** with:
   - Clear title describing the change
   - Description of what was added/changed
   - Test results
   - Any relevant screenshots or examples

## Code Review Checklist

Before requesting review, ensure:
- [ ] All tests pass
- [ ] No hardcoded credentials
- [ ] Type hints on all functions
- [ ] Docstrings on all public APIs
- [ ] New engines have functional tests
- [ ] Code follows the existing patterns

## Security

- **Never commit API keys, passwords, or secrets**
- **Use `.env.example` as a template** for environment variables
- **Report security issues** privately, not via public issues
- **Redact secrets** in logs and error messages

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
