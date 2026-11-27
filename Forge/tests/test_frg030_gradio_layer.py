"""
Tests for TASK-FRG-030: Gradio instant-UI delivery layer + board lookup tool.
"""

import pytest

gradio = pytest.importorskip("gradio")

from app.delivery.board_lookup_tool import (
    list_owners,
    lookup_board_tasks,
    board_lookup_spec,
)
from app.delivery.gradio_layer import (
    GRADIO_RULE,
    ToolSpec,
    build_interface,
)

SAMPLE_BOARD = """schema_version: 1
tasks:
  - id: TASK-FRG-030
    title: 'Forge: Gradio instant-UI delivery layer'
    status: AVAILABLE
    owner: muse_11
    branch: null
    pr: null
  - id: TASK-FRG-021
    title: 'Forge: per-interface binding in downloader'
    status: AVAILABLE
    owner: muse_11
    branch: null
    pr: null
  - id: TASK-STR-078
    title: 'REPO-IMPLEMENT: Stratex repos'
    status: CLAIMED
    owner: muse_11
    branch: muse11/task-str-078-repo-implement
    pr: null
  - id: TASK-MEM-027
    title: 'Memora: three-section live proof run 4'
    status: AVAILABLE
    owner: muse_11
    branch: null
    pr: null
"""


@pytest.fixture()
def board_file(tmp_path):
    path = tmp_path / "WORK_BOARD.yaml"
    path.write_text(SAMPLE_BOARD, encoding="utf-8")
    return path


def test_lookup_by_id_substring(board_file):
    out = lookup_board_tasks("FRG-030", board_path=board_file)
    assert "TASK-FRG-030" in out
    assert "TASK-FRG-021" not in out
    assert "1 matched" in out


def test_lookup_by_status_and_owner(board_file):
    out = lookup_board_tasks("", "AVAILABLE", "muse_11", board_path=board_file)
    assert "3 matched" in out
    assert "TASK-STR-078" not in out


def test_lookup_no_match(board_file):
    out = lookup_board_tasks("NOPE-999", board_path=board_file)
    assert "0 matched" in out
    assert "No matching tasks." in out


def test_lookup_max_rows_capped(board_file):
    out = lookup_board_tasks("", "ANY", "ANY", 2, board_path=board_file)
    assert "… and 2 more" in out
    assert "TASK-MEM-027" not in out  # beyond the cap


def test_list_owners(board_file):
    assert list_owners(board_file) == ["ANY", "muse_11"]


def test_gradio_rule_recorded():
    assert "single-purpose" in GRADIO_RULE
    assert "full app" in GRADIO_RULE


def test_build_interface_for_lookup(board_file):
    spec = board_lookup_spec(board_file)
    assert isinstance(spec, ToolSpec)
    iface = build_interface(spec)
    assert isinstance(iface, gradio.Interface)
    # Gradio 6 renamed inputs/outputs -> input_components/output_components.
    inputs = getattr(iface, "input_components", getattr(iface, "inputs", None))
    outputs = getattr(iface, "output_components", getattr(iface, "outputs", None))
    assert len(inputs) == 4  # task id, status, owner, max rows
    assert len(outputs) == 1
    # The interface function is the real lookup: call it directly.
    out = iface.fn("FRG-021", "ANY", "ANY", 10)
    assert "TASK-FRG-021" in out


def test_build_interface_rejects_unknown_kind():
    spec = ToolSpec(
        name="bad",
        description="bad",
        fn=lambda: "x",
        inputs=[{"kind": "carousel", "label": "Nope"}],
    )
    with pytest.raises(ValueError, match="unknown input kind"):
        build_interface(spec)
