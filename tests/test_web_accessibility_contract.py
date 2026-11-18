"""Dependency-free source contracts; Chromium verification is a separate gate."""
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "ai_model_advisor" / "web"
HTML = (WEB / "index.html").read_text(encoding="utf-8")
CSS = (WEB / "app.css").read_text(encoding="utf-8")
JS = (WEB / "app.js").read_text(encoding="utf-8")


def test_hidden_recommendations_are_really_hidden():
    assert 'id="results"' in HTML
    assert HTML.split('id="results"', 1)[1].split('>', 1)[0].rstrip().endswith(' hidden')
    assert '[hidden]{display:none!important}' in CSS
    assert '$("results").hidden=true' in JS


def test_navigation_and_async_screen_reader_flow():
    assert 'href="#main-content">Skip to main content</a>' in HTML
    assert 'id="main-content"' in HTML
    assert 'id="request-status"' in HTML and 'aria-live="polite"' in HTML
    assert 'id="primary-name" tabindex="-1"' in HTML
    assert 'id="task" aria-describedby="form-error"' in HTML
    assert 'task.setAttribute("aria-invalid","true")' in JS
    assert 'task.removeAttribute("aria-invalid")' in JS
    assert '$("primary-name").focus({preventScroll:true})' in JS
    assert 'error.focus()' in JS


def test_loading_control_preserves_button_semantics():
    assert 'id="submit-label"' in HTML
    assert '$("submit-label").textContent="Finding..."' in JS
    assert 'submit.replaceChildren()' not in JS
    assert '.request-status:empty{height:0' in CSS


def test_reflow_forced_colors_and_reduced_motion_contract():
    assert 'min-width:0' in CSS
    assert 'text-overflow:ellipsis' in CSS
    assert '@media(forced-colors:active)' in CSS
    assert '.segments input:checked+span{outline:2px solid Highlight' in CSS
    assert 'prefers-reduced-motion: reduce' in JS
    assert '.skip-link:focus-visible' in CSS
    assert 'footer span{display:block}' in CSS
