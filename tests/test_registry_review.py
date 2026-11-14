import json
import subprocess
import sys

import pytest

from tools.ai_model_advisor.registry_review import issue_body, review_signals


def test_review_normalizes_and_deduplicates_untrusted_signals():
    signals = review_signals({
        "new_unknown_signals": [
            " GPT-6.1 Terra ", "Claude Sonnet 4.5", "GPT-6.1   Terra",
            "<injected>*model*", "",
        ]
    })
    assert signals == [
        "&lt;injected&gt;\\*model\\*", "Claude Sonnet 4.5", "GPT-6.1 Terra"
    ]
    assert review_signals({"new_unknown_signals": []}) == []


def test_report_schema_fail_closed():
    with pytest.raises(ValueError, match="array"):
        review_signals({"new_unknown_signals": "wrong"})
    with pytest.raises(ValueError, match="strings"):
        review_signals({"new_unknown_signals": [42]})
    with pytest.raises(ValueError, match="object"):
        review_signals([])


def test_issue_requires_review_and_preserves_human_gate():
    body = issue_body(["GPT-6.1 Terra"])
    assert "GPT-6.1 Terra" in body
    assert "not confirmed model releases" in body
    assert "do not auto-promote models" in body
    with pytest.raises(ValueError, match="without signals"):
        issue_body([])


def test_cli_generates_stable_review_files(tmp_path):
    source = tmp_path / "scan.json"
    source.write_text(json.dumps({
        "new_unknown_signals": ["GPT-6.1 Terra", "Claude Sonnet 4.5"]
    }), encoding="utf-8")
    body = tmp_path / "issue.md"
    output = tmp_path / "review.json"
    args = [
        sys.executable, "-m", "tools.ai_model_advisor.registry_review",
        "--report", str(source), "--body", str(body), "--output", str(output)
    ]
    subprocess.run(args, check=True, capture_output=True, text=True)
    first = body.read_text(encoding="utf-8")
    subprocess.run(args, check=True, capture_output=True, text=True)
    assert body.read_text(encoding="utf-8") == first
    assert json.loads(output.read_text())["review_required"] is True
    source.write_text(json.dumps({"new_unknown_signals": []}), encoding="utf-8")
    subprocess.run(args, check=True, capture_output=True, text=True)
    assert body.read_text() == ""
    assert json.loads(output.read_text())["review_required"] is False
