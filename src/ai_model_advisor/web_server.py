"""Local-only, zero-dependency web interface for AI Model Advisor.

The UI recommends configurations; it does not call paid model providers,
persist task text, or apply any routing changes.
"""
from __future__ import annotations

import argparse
import json
import math
import secrets
import time
from pathlib import Path
from threading import Lock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any
from urllib.parse import urlsplit

from . import __version__
from .api import Advisor

MAX_BODY_BYTES = 16_384
MAX_TASK_CHARS = 6_000
DECISION_TTL_SECONDS = 24 * 60 * 60
MAX_PENDING_DECISIONS = 128
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
PRIORITIES = {
    "balanced": (3.0, 3.0),
    "quality": (1.0, 1.0),
    "cost": (5.0, 2.0),
    "speed": (2.0, 5.0),
}


def _valid_host(value: str) -> bool:
    """Only permit loopback Host headers to prevent local DNS rebinding."""
    if not value:
        return False
    try:
        parsed = urlsplit("//" + value)
        return parsed.hostname in {"127.0.0.1", "localhost"} and (
            parsed.port is None or 1 <= parsed.port <= 65535
        ) and not parsed.username and not parsed.password
    except ValueError:
        return False


def parse_decision_request(payload: Any) -> tuple[str, str, str]:
    if not isinstance(payload, dict) or set(payload) != {"task", "provider", "priority"}:
        raise ValueError("Send task, provider, and priority.")
    task = payload["task"]
    if not isinstance(task, str) or not task.strip():
        raise ValueError("Describe the task to get a recommendation.")
    if len(task) > MAX_TASK_CHARS:
        raise ValueError(f"Keep your task under {MAX_TASK_CHARS:,} characters.")
    provider = payload["provider"]
    priority = payload["priority"]
    if provider not in ("all", "openai", "anthropic"):
        raise ValueError("Choose All providers, OpenAI, or Anthropic.")
    if priority not in PRIORITIES:
        raise ValueError("Choose a supported optimization priority.")
    return task.strip(), provider, priority



def parse_feedback_request(
    payload: Any,
) -> tuple[str, str, str, float | None, float | None]:
    """Only accept a server-issued decision ID and observed outcome/metrics."""
    required = {"decision_id", "configuration", "outcome"}
    optional = {"cost_usd", "latency_seconds"}
    if not isinstance(payload, dict) or not required <= payload.keys():
        raise ValueError("Choose the configuration used and its outcome.")
    if set(payload) - required - optional:
        raise ValueError("Unsupported feedback fields.")
    decision_id = payload["decision_id"]
    configuration = payload["configuration"]
    outcome = payload["outcome"]
    if not isinstance(decision_id, str) or not 20 <= len(decision_id) <= 128:
        raise ValueError("The recommendation session is invalid.")
    if configuration not in ("primary", "cheaper_fallback", "escalation"):
        raise ValueError("Choose the configuration you actually used.")
    if outcome not in ("success", "partial", "failure"):
        raise ValueError("Choose Success, Partial, or Failure.")
    values = []
    for key in ("cost_usd", "latency_seconds"):
        value = payload.get(key)
        if value is not None:
            if (
                type(value) not in (float, int)
                or not math.isfinite(value)
                or value < 0
                or (key == "latency_seconds" and value <= 0)
            ):
                raise ValueError(f"{key} must be a valid positive number.")
        values.append(float(value) if value is not None else None)
    return decision_id, configuration, outcome, values[0], values[1]


def _category_of(decision: Any) -> str | None:
    categories = decision.profile.categories
    return (
        max(categories, key=lambda name: (categories[name], name))
        if categories else None
    )


def _choices_of(decision: Any) -> dict[str, dict[str, str]]:
    candidates = {
        "primary": decision.primary,
        "cheaper_fallback": decision.cheaper_fallback,
        "escalation": decision.escalation,
    }
    return {
        name: {
            "provider": record.provider,
            "model_id": record.model_id,
            "effort": record.effort,
            "execution_mode": record.execution_mode,
        }
        for name, record in candidates.items()
        if record is not None
    }

def make_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    advisor: Advisor | None = None,
    feedback_path: str | Path | None = None,
) -> ThreadingHTTPServer:
    """Build a testable HTTP server; intentionally rejects remote interfaces."""
    if host != "127.0.0.1":
        raise ValueError("The unauthenticated web UI may only bind to 127.0.0.1.")
    if advisor is not None and feedback_path is not None:
        raise ValueError("Pass either an Advisor or a feedback_path, not both.")
    path = Path(feedback_path) if feedback_path is not None else (
        Path.home() / ".ai-model-advisor" / "feedback.jsonl"
    )
    app = advisor if advisor is not None else Advisor(feedback=path)
    assets = files("ai_model_advisor").joinpath("web")
    pending: dict[str, tuple[float, str | None, dict[str, dict[str, str]]]] = {}
    feedback_lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "AIModelAdvisor"
        sys_version = ""

        def log_message(self, format_string: str, *args: Any) -> None:
            # Deliberately never log user task text or any request body.
            return

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "img-src 'self'; connect-src 'self'; base-uri 'none'; "
                "form-action 'self'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(status, data, "application/json; charset=utf-8")

        def _host_allowed(self) -> bool:
            if not _valid_host(self.headers.get("Host", "")):
                self._json(403, {"error": "This interface only accepts local requests."})
                return False
            return True

        def do_GET(self) -> None:
            if not self._host_allowed():
                return
            path = urlsplit(self.path).path
            if path == "/api/meta":
                self._json(
                    200,
                    {
                        "version": __version__,
                        "registry_as_of": app.registry_as_of,
                        "current_models": len(app.models()),
                        "mode": "local",
                        "provider_calls": False,
                        "feedback_records": len(app.feedback.records),
                    },
                )
                return
            item = ASSETS.get(path)
            if item is None:
                self._json(404, {"error": "Page not found."})
                return
            filename, content_type = item
            self._send(200, assets.joinpath(filename).read_bytes(), content_type)

        def do_POST(self) -> None:
            if not self._host_allowed():
                return
            route = urlsplit(self.path).path
            if route not in ("/api/decide", "/api/feedback"):
                self._json(404, {"error": "Endpoint not found."})
                return
            host_header = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if origin and origin not in (
                f"http://{host_header}",
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            ):
                self._json(403, {"error": "Cross-origin requests are not allowed."})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip() != (
                "application/json"
            ):
                self._json(415, {"error": "Please send JSON."})
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json(400, {"error": "Invalid request length."})
                return
            if content_length < 1 or content_length > MAX_BODY_BYTES:
                self._json(413, {"error": "Request body is too large or empty."})
                return
            try:
                payload = json.loads(self.rfile.read(content_length))
                if route == "/api/decide":
                    task, provider, priority = parse_decision_request(payload)
                    cost, latency = PRIORITIES[priority]
                    decision = app.decide_task(
                        task,
                        providers=None if provider == "all" else (provider,),
                        cost_sensitivity=cost,
                        latency_sensitivity=latency,
                    )
                    token = secrets.token_urlsafe(24)
                    now = time.monotonic()
                    with feedback_lock:
                        for old in list(pending):
                            if pending[old][0] < now:
                                pending.pop(old)
                        if len(pending) >= MAX_PENDING_DECISIONS:
                            oldest = min(pending, key=lambda key: pending[key][0])
                            pending.pop(oldest)
                        options = _choices_of(decision)
                        pending[token] = (
                            now + DECISION_TTL_SECONDS, _category_of(decision), options
                        )
                    self._json(
                        200,
                        {
                            "decision": decision.as_dict(),
                            "decision_id": token,
                            "feedback_options": list(options),
                            "provider_calls": False,
                        },
                    )
                    return

                token, used, outcome, cost, latency = parse_feedback_request(payload)
                with feedback_lock:
                    entry = pending.get(token)
                    if entry is None or entry[0] <= time.monotonic():
                        pending.pop(token, None)
                        self._json(
                            409,
                            {"error": "This recommendation expired. Run it again to give feedback."},
                        )
                        return
                    _, category, choices = entry
                    selected = choices.get(used)
                    if selected is None:
                        self._json(400, {"error": "That configuration was not offered."})
                        return
                    app.record_outcome(
                        provider=selected["provider"],
                        model_id=selected["model_id"],
                        effort=selected["effort"],
                        execution_mode=selected["execution_mode"],
                        outcome=outcome,
                        task_category=category,
                        task_id="web-" + secrets.token_hex(12),
                        cost_usd=cost,
                        latency_seconds=latency,
                    )
                    pending.pop(token, None)
                    count = len(app.feedback.records)
                self._json(
                    200,
                    {"saved": True, "feedback_records": count, "provider_calls": False},
                )
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})
            except Exception:
                # No tracebacks, feedback paths, user input or secrets in the UI.
                self._json(500, {"error": "Request failed. Check the local server."})

    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local AI Model Advisor web UI")
    parser.add_argument("--port", type=int, default=8765, help="Local port (default: 8765)")
    parser.add_argument(
        "--feedback", type=Path,
        help="Local JSONL for explicitly submitted outcomes (default: ~/.ai-model-advisor/feedback.jsonl)",
    )
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("--port must be in the range 0..65535")
    with make_server(port=args.port, feedback_path=args.feedback) as server:
        print(f"AI Model Advisor is ready at http://127.0.0.1:{server.server_port}")
        print("Local only. No provider API calls; outcomes saved only when submitted.")
        print("Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
