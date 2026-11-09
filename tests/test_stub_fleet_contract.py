"""The stub fleet must enforce the wire contract, or tests that use it prove nothing."""
import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

import stub_fleet

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def stub():
    server, port = stub_fleet.start_stub_fleet()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def envelope(agent="Inference", action="reason", **over):
    body = {"task_id": "t1", "agent": agent, "action": action, "payload": {},
            "priority": "100", "source_agent": "FRIDAY"}
    body.update(over)
    return body


def post(stub, path, body):
    return httpx.post(stub + path, json=body, timeout=5)


def test_valid_envelope_succeeds_and_is_marked_as_stub(stub):
    r = post(stub, "/inference/v1/task/execute", envelope())
    assert r.status_code == 200 and r.json()["status"] == "SUCCESS" and r.json()["result"]["stub"] is True


def test_wrong_route_is_404(stub):
    assert post(stub, "/inference/agent/inference/reason", envelope()).status_code == 404
    assert post(stub, "/nonexistent/v1/task/execute", envelope()).status_code == 404


def test_vyralx_uses_its_own_route_only(stub):
    assert post(stub, "/vyralx/api/v1/tasks", {"topic": "x"}).status_code == 200
    assert post(stub, "/vyralx/v1/task/execute", envelope("VyralX", "create_content")).status_code == 404


def test_unsupported_action_is_rejected(stub):
    r = post(stub, "/inference/v1/task/execute", envelope(action="definitely_not_an_action"))
    assert r.status_code == 422 and r.json()["error"] == "unsupported_action"


def test_action_must_belong_to_the_agent(stub):
    assert post(stub, "/memora/v1/task/execute", envelope("Memora", "scan_threats")).status_code == 422


def test_envelope_must_be_complete_and_typed(stub):
    for bad in ({"priority": 100}, {"payload": "x"}, {"task_id": None}, {"source_agent": 5}):
        assert post(stub, "/inference/v1/task/execute", envelope(**bad)).status_code == 422, bad
    assert post(stub, "/inference/v1/task/execute", envelope(agent="Memora")).status_code == 422


def test_non_object_and_invalid_json_are_rejected(stub):
    assert post(stub, "/inference/v1/task/execute", ["a"]).status_code == 422
    r = httpx.post(stub + "/inference/v1/task/execute", content=b"{nope", headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_health_only_on_health_route(stub):
    assert httpx.get(stub + "/inference/health").status_code == 200
    assert httpx.get(stub + "/inference/anything").status_code == 404


def test_modes_never_mix_and_misuse_fails():
    with pytest.raises(ValueError, match="already set"):
        stub_fleet.configure_fleet({"FRIDAY_DISPATCH_INFERENCE_URL": "http://x"})
    with pytest.raises(ValueError, match="missing"):
        stub_fleet.configure_fleet({"FRIDAY_TEST_FLEET": "live", "FRIDAY_DISPATCH_INFERENCE_URL": "http://x"})
    with pytest.raises(ValueError, match="must be"):
        stub_fleet.configure_fleet({"FRIDAY_TEST_FLEET": "maybe"})
    env = {"FRIDAY_TEST_FLEET": "live", **{v: "http://real" for v in stub_fleet.FLEET_URL_VARS}}
    assert stub_fleet.configure_fleet(env) == ("live", None)


def test_bus_reports_failure_for_an_unsupported_action(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "bus_under_test", ROOT / "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py")
    assert spec is not None and spec.loader is not None
    bus_mod = importlib.util.module_from_spec(spec)
    # dataclasses resolves postponed annotations through sys.modules. Modules created with
    # module_from_spec() must be registered before exec_module() for that lookup to work.
    monkeypatch.setitem(sys.modules, spec.name, bus_mod)
    spec.loader.exec_module(bus_mod)
    bus = bus_mod.UniverseDispatchBus()
    receipt = bus.dispatch("Inference", "definitely_not_an_action", {})
    assert receipt.status == "failed" and "422" in receipt.error
