"""No-network guardrails for the reused decision comparison UI pattern."""
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "ai_model_advisor" / "web"

class IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
    def handle_starttag(self, tag, attrs):
        self.ids.extend(value for key, value in attrs if key == "id")

def test_decision_comparison_semantics_and_no_duplicate_ids():
    page = (WEB / "index.html").read_text(encoding="utf-8")
    parser = IdParser()
    parser.feed(page)
    assert len(parser.ids) == len(set(parser.ids))
    for marker in ("decision-matrix-body", "decision-matrix-title", "decision-caveat"):
        assert marker in page
    assert 'scope="col"' in page and 'role="region"' in page
    assert 'SUGGESTED' in page
    assert 'BEST FIT' not in page

def test_comparison_is_local_text_only_and_uses_no_new_api():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    css = (WEB / "app.css").read_text(encoding="utf-8")
    assert 'renderComparison(d)' in js
    assert 'cell.textContent=String(value)' in js
    assert 'decision.cheaper_fallback' in js and 'decision.escalation' in js
    assert 'decision-matrix__scroll:focus-visible' in css
    assert '@media(max-width:620px)' in css
    assert 'fetch("/api/decide"' in js
    assert 'fetch("/api/feedback"' in js
    assert 'fetch("/api/meta")' in js
    assert 'script src="/app.js"' in (WEB / "index.html").read_text(encoding="utf-8")
