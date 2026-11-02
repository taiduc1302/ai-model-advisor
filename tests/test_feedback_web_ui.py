import http.client
import json
import threading

import pytest

from ai_model_advisor.web_server import make_server


@pytest.fixture
def server(tmp_path):
    instance = make_server(port=0, feedback_path=tmp_path / "observations.jsonl")
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance, tmp_path / "observations.jsonl"
    instance.shutdown()
    instance.server_close()
    thread.join(timeout=3)


def post(server, route, body, origin=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    conn.request("POST", route, json.dumps(body), headers)
    result = conn.getresponse()
    status, payload = result.status, json.loads(result.read())
    conn.close()
    return status, payload


def decide(server):
    status, result = post(server, "/api/decide", {
        "task": "Audit this repository and fix failing tests",
        "provider": "all", "priority": "balanced",
    })
    assert status == 200
    return result


def test_feedback_round_trip_persists_without_task_text(server):
    instance, path = server
    decision = decide(instance)
    assert "primary" in decision["feedback_options"]
    assert len(decision["decision_id"]) >= 20
    status, saved = post(instance, "/api/feedback", {
        "decision_id": decision["decision_id"],
        "configuration": "primary", "outcome": "partial",
        "latency_seconds": 28.5, "cost_usd": 0.25,
    })
    assert status == 200
    assert saved["saved"] is True
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["outcome"] == "partial"
    assert rows[0]["model_id"] == decision["decision"]["primary"]["model_id"]
    assert rows[0]["latency_seconds"] == 28.5
    assert rows[0]["cost_usd"] == 0.25
    assert rows[0]["task_id"].startswith("web-")
    assert "Audit this repository" not in path.read_text(encoding="utf-8")
    status, _ = post(instance, "/api/feedback", {
        "decision_id": decision["decision_id"],
        "configuration": "primary", "outcome": "success",
    })
    assert status == 409
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


@pytest.mark.parametrize("field,value", [
    ("outcome", "excellent"),
    ("configuration", "arbitrary"),
    ("latency_seconds", -5),
    ("cost_usd", -1),
    ("cost_usd", "free"),
])
def test_invalid_feedback_rejected_without_write(server, field, value):
    instance, path = server
    issued = decide(instance)
    payload = {
        "decision_id": issued["decision_id"],
        "configuration": "primary", "outcome": "success",
    }
    payload[field] = value
    status, _ = post(instance, "/api/feedback", payload)
    assert status == 400
    assert not path.exists()


def test_unknown_token_and_foreign_origin_denied(server):
    instance, path = server
    status, _ = post(instance, "/api/feedback", {
        "decision_id": "X" * 32, "configuration": "primary", "outcome": "success",
    })
    assert status == 409
    issued = decide(instance)
    status, _ = post(instance, "/api/feedback", {
        "decision_id": issued["decision_id"],
        "configuration": "primary", "outcome": "success",
    }, origin="https://evil.example")
    assert status == 403
    assert not path.exists()
