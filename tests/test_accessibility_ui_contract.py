"""Dependency-free static regression checks for accessible local web states."""
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "ai_model_advisor" / "web"
HTML = (WEB / "index.html").read_text(encoding="utf-8")
CSS = (WEB / "app.css").read_text(encoding="utf-8")
JS = (WEB / "app.js").read_text(encoding="utf-8")


def test_hidden_attribute_wins_over_grid_and_state_styles():
    assert "[hidden]{display:none!important}" in CSS
    assert 'id="results"' in HTML and 'id="empty"' in HTML
    assert 'id="loading"' in HTML and 'role="status" hidden' in HTML


def test_keyboard_and_focus_return_to_recommendation():
    assert 'class="skip-link" href="#task"' in HTML
    assert 'id="primary-name" tabindex="-1"' in HTML
    assert '$("primary-name").focus({preventScroll:true})' in JS
    assert ".skip-link:focus" in CSS


def test_forced_colors_native_radio_selection_available():
    assert '@media(forced-colors:active)' in CSS
    assert '.segments input{position:static;inset:auto;opacity:1;' in CSS
    assert '.segments input:checked+span' in CSS


def test_loading_and_failure_clear_stale_results():
    assert '$("loading").hidden=false' in JS
    assert '$("loading").hidden=true' in JS
    assert '$("results").hidden=true' in JS
    assert '$("empty").hidden=false' in JS
    assert 'current=null;currentToken=null' in JS
    assert 'id="form-error" class="error" role="alert"' in HTML


def test_existing_local_endpoints_are_preserved():
    assert 'fetch("/api/meta")' in JS
    assert 'fetch("/api/decide"' in JS
    assert 'fetch("/api/feedback"' in JS
    assert 'task.value.trim()' in JS
