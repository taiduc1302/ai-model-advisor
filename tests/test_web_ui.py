"""Local UI tests: no paid provider calls and no browser dependencies."""
import http.client
import json
import threading

import pytest

from ai_model_advisor.web_server import (
    MAX_TASK_CHARS,
    make_server,
    parse_decision_request,
)


@pytest.fixture
def local_server():
    server = make_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def request(server, method, path, body=None, *, host="127.0.0.1", headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    data = json.dumps(body) if body is not None else None
    options = {"Host": host}
    if data is not None:
        options["Content-Type"] = "application/json"
    if headers:
        options.update(headers)
    conn.request(method, path, body=data, headers=options)
    response = conn.getresponse()
    result = response.read()
    status = response.status
    response_headers = dict(response.getheaders())
    conn.close()
    return status, result, response_headers


def test_web_assets_and_security_headers(local_server):
    for path in ("/", "/app.css", "/app.js", "/favicon.svg"):
        status, body, headers = request(local_server, "GET", path)
        assert status == 200 and body
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "default-src 'none'" in headers["Content-Security-Policy"]
    status, body, _ = request(local_server, "GET", "/")
    assert b"Find the right AI" in body


def test_local_meta_and_real_routing(local_server):
    code, body, _ = request(local_server, "GET", "/api/meta")
    meta = json.loads(body)
    assert code == 200
    assert meta["provider_calls"] is False
    assert meta["current_models"] > 0
    status, body, _ = request(
        local_server,
        "POST",
        "/api/decide",
        {"task": "Audit the repository, find failing tests, and fix errors.",
         "provider": "openai", "priority": "quality"},
    )
    payload = json.loads(body)
    assert status == 200
    assert payload["provider_calls"] is False
    assert payload["decision"]["primary"]["provider"] == "openai"
    assert payload["decision"]["escalation_triggers"]
    assert payload["decision"]["personal_evidence"]


@pytest.mark.parametrize("payload", [
    {},
    {"task": "", "provider": "all", "priority": "balanced"},
    {"task": "x" * (MAX_TASK_CHARS + 1), "provider": "all", "priority": "balanced"},
    {"task": "fix a bug", "provider": "evil", "priority": "balanced"},
    {"task": "fix a bug", "provider": "all", "priority": "invalid"},
    {"task": "fix", "provider": "all", "priority": "balanced", "unexpected": 1},
])
def test_invalid_requests_rejected(payload):
    with pytest.raises(ValueError):
        parse_decision_request(payload)


def test_rejects_remote_bind():
    with pytest.raises(ValueError, match="127.0.0.1"):
        make_server(host="0.0.0.0", port=0)


def test_host_origin_and_unknown_endpoints(local_server):
    status, _, _ = request(local_server, "GET", "/", host="evil.example")
    assert status == 403
    status, _, _ = request(
        local_server, "POST", "/api/decide",
        {"task": "test", "provider": "all", "priority": "balanced"},
        headers={"Origin": "http://evil.example"},
    )
    assert status == 403
    status, _, _ = request(local_server, "GET", "/unknown")
    assert status == 404
    status, _, _ = request(local_server, "POST", "/missing", {})
    assert status == 404


def test_oversized_post_is_rejected(local_server):
    status, _, _ = request(local_server, "POST", "/api/decide", {
        "task": "x" * 20000,
        "provider": "all",
        "priority": "balanced",
    })
    assert status == 413
