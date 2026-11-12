"""Conservative Python replacement validation before a model can touch source.

This is not behavior verification: the coordinator must run the real suite again.
Unsupported/ambiguous changes are left for a human rather than weakening tests.
"""
from __future__ import annotations

import ast
import copy
from pathlib import PurePosixPath


MAX_REPAIR_SOURCE = 32000
MAX_REPAIR_FILES = 3


def is_test_path(path: str) -> bool:
    p = PurePosixPath(path)
    return 'tests' in p.parts or p.name.startswith('test_') or p.name.endswith('_test.py')


def _protected_ast(node: ast.AST, module: ast.Module, *, allow_private: bool = True) -> str:
    """Compare tests modulo ONE equivalent public stdlib import correction.

    pathlib.os is an accidental export removed in Python 3.13. Replacing that
    module reference with an explicit import of os does not change assertions,
    fixture logic or test selection. No source is rewritten by this function.
    Ambiguous/shadowed bindings disable normalization and fail closed.
    """
    marker = "__forge_public_stdlib_os__"
    imports = {}
    top_imports = set()
    for item in module.body:
        if isinstance(item, ast.Import):
            top_imports.add(id(item))
            for alias in item.names:
                bound = alias.asname or alias.name.split(".")[0]
                if bound in imports and imports[bound] != alias.name:
                    return ast.dump(node)
                imports[bound] = alias.name
    imports = {name: target for name, target in imports.items() if target in {"pathlib", "os"}}
    shadowed = set()
    for item in ast.walk(module):
        if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del)):
            shadowed.add(item.id)
        elif isinstance(item, (ast.Attribute, ast.Subscript)) and isinstance(item.ctx, (ast.Store, ast.Del)):
            shadowed.update(n.id for n in ast.walk(item) if isinstance(n, ast.Name))
        elif isinstance(item, ast.arg):
            shadowed.add(item.arg)
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            shadowed.add(item.name)
        elif isinstance(item, ast.ExceptHandler) and item.name:
            shadowed.add(item.name)
        elif isinstance(item, ast.ImportFrom) or isinstance(item, ast.Import) and id(item) not in top_imports:
            for alias in item.names:
                if alias.name == "*":
                    return ast.dump(node)
                shadowed.add(alias.asname or alias.name.split(".")[0])
        if isinstance(item, ast.Name) and item.id == marker:
            return ast.dump(node)
    if shadowed.intersection(imports):
        return ast.dump(node)

    class PublicOS(ast.NodeTransformer):
        def visit_Attribute(self, item):
            if (allow_private and isinstance(item.value, ast.Name) and item.attr == "os"
                    and imports.get(item.value.id) == "pathlib"):
                return ast.copy_location(ast.Name(id=marker, ctx=item.ctx), item)
            return self.generic_visit(item)

        def visit_Name(self, item):
            if isinstance(item.ctx, ast.Load) and imports.get(item.id) == "os":
                return ast.copy_location(ast.Name(id=marker, ctx=item.ctx), item)
            return item

    return ast.dump(PublicOS().visit(copy.deepcopy(node)))


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
        if (protected and ast.dump(node) != ast.dump(other)
                and _protected_ast(node, old) != _protected_ast(other, new, allow_private=False)):
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
