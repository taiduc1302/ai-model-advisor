import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vercel_auto_deploy_is_explicitly_disabled():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["git"]["deploymentEnabled"] is False


def test_monitor_uses_human_review_not_failure_exit():
    text = (ROOT / ".github/workflows/model-registry-monitor.yml").read_text()
    assert "tools.ai_model_advisor.registry_review" in text
    assert "gh issue create" in text
    assert "gh issue edit" in text
    assert "raise SystemExit(2)" not in text
    assert "issues: write" in text
    assert 'cron: "17 15 * * 1"' in text
