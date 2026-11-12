"""Conservative Python replacement validation before a model can touch source.

This is not behavior verification: the coordinator must run the real suite again.
Unsupported/ambiguous changes are left for a human rather than weakening tests.
"""
from __future__ import annotations

import ast
from pathlib import PurePosixPath


MAX_REPAIR_SOURCE = 32000
MAX_REPAIR_FILES = 3


def is_test_path(path: str) -> bool:
    p = PurePosixPath(path)
    return 'tests' in p.parts or p.name.startswith('test_') or p.name.endswith('_test.py')


def validate_replacement(original: str, candidate: str) -> str | None:
    """Return a rejection reason, or None for a source-preserving candidate."""
    if not candidate.strip() or candidate.strip() == original.strip():
        return 'empty_or_unchanged'
    if len(candidate) > MAX_REPAIR_SOURCE:
        return 'replacement_too_large'
    try:
        old = ast.parse(original)
        new = ast.parse(candidate)
    except (SyntaxError, ValueError):
        return 'unparseable_source'

    def definitions(tree):
        found = {}
        def visit(nodes, prefix=''):
            for node in nodes:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    key = prefix + node.name
                    found[key] = node
                    if isinstance(node, ast.ClassDef):
                        visit(node.body, key + '.')
        visit(tree.body)
        return found

    old_defs, new_defs = definitions(old), definitions(new)
    for key, node in old_defs.items():
        other = new_defs.get(key)
        if other is None or type(node) is not type(other):
            return 'definition_removed_or_retyped:' + key
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if ast.dump(node.args) != ast.dump(other.args):
                return 'signature_changed:' + key
        # Protect all test functions and entire classes containing tests,
        # including aliased TestCase bases, decorators and setup/teardown.
        protected = node.name.startswith('test_') or (
            isinstance(node, ast.ClassDef) and any(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test_')
                for n in ast.walk(node)
            )
        )
        if protected and ast.dump(node) != ast.dump(other):
            return 'test_changed:' + key
    return None


async def repair_with_inference(task_id, context, engine, role='debugger'):
    """Ask the real code endpoint for bounded replacements, then validate them.

    Never regenerate the manifest or use deterministic unrelated synthesis. A
    proposed change is not a verified repair until the coordinator re-tests it.
    """
    from app.agents.parser import LLMResponseParser
    from app.integrations.ai_universe_client import get_ai_universe_client

    result = {'status': 'failed', 'fixed_files': [], 'rejections': [],
              'agent': role, 'verification_required': True}
    goal = str(context.get('goal', '')).strip()
    if not goal:
        result['rejections'].append('missing_objective')
        return result
    originals = {}
    for path in context.get('project_files', []):
        if not isinstance(path, str) or not path.endswith('.py') or is_test_path(path):
            continue
        try:
            source = engine.fs.read_file(task_id, path, role=role)
            if len(source) > MAX_REPAIR_SOURCE:
                result['rejections'].append('source_too_large:' + path)
                continue
            ast.parse(source)
        except (SyntaxError, ValueError, OSError):
            result['rejections'].append('unreadable_or_unparseable:' + path)
            continue
        originals[path] = source
        if len(originals) == MAX_REPAIR_FILES:
            break
    if not originals:
        return result
    client = get_ai_universe_client()
    for path, original in originals.items():
        try:
            reply = await client.generate_code(
                filename=path, goal=goal, file_type='python',
                requirements=[*context.get('requirements', []),
                              'Repair existing implementation minimally. Preserve every existing test and public API. '
                              'Do not change tests, invent unrelated scaffolds, push, or deploy.'],
                context={'project_goal': goal, 'repair': {
                    'original_source': original,
                    'failure_evidence': str(context.get('error', ''))[-12000:],
                }},
            )
            if not reply or reply.confidence < 0.7:
                result['rejections'].append('unavailable_or_low_confidence:' + path)
                continue
            files = LLMResponseParser.extract_files(reply.answer, default_filename=path)
            if len(files) != 1 or files[0].relative_path != path:
                result['rejections'].append('unexpected_file_set:' + path)
                continue
            replacement = files[0].content
            reason = validate_replacement(original, replacement)
            if reason:
                result['rejections'].append(reason + ':' + path)
                continue
            if engine.fs.read_file(task_id, path, role=role) != original:
                result['rejections'].append('source_changed_during_request:' + path)
                continue
            engine.fs.create_file(task_id=task_id, relative_path=path,
                                  content=replacement, role=role)
            result['fixed_files'].append(path)
        except Exception as exc:
            # Log only exception class: provider errors can carry credentials.
            result['rejections'].append(type(exc).__name__ + ':' + path)
    if result['fixed_files']:
        result['status'] = 'success'
    return result
