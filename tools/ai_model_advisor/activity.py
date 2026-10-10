from __future__ import annotations

import json
import re
import urllib.request
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import WorkloadProfile

CATEGORY_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "implementation": (
        (r"\bimplement(?:ation)?\b", "implement"),
        (r"\bbuild\b", "build"),
        (r"\bdevelop\b", "develop"),
        (r"\bfeature\b", "feature"),
        (r"\bcode\b", "code"),
        (r"\bendpoint\b", "endpoint"),
        (r"\bapi\b", "api"),
        (r"\bfrontend\b", "frontend"),
        (r"\bbackend\b", "backend"),
        (r"\bscript\b", "script"),
        (r"\bfunction\b", "function"),
        (r"\bclass\b", "class"),
    ),
    "debugging": (
        (r"\bdebug(?:ging)?\b", "debug"),
        (r"\bbugs?\b", "bug"),
        (r"\berrors?\b", "error"),
        (r"\bexception\b", "exception"),
        (r"\btraceback\b", "traceback"),
        (r"\bfailing tests?\b", "failing test"),
        (r"\bregression\b", "regression"),
        (r"\broot cause\b", "root cause"),
        (r"\bfix\b", "fix"),
    ),
    "architecture": (
        (r"\barchitecture\b", "architecture"),
        (r"\barchitectural\b", "architectural"),
        (r"\bsystem design\b", "system design"),
        (r"\brefactor\b", "refactor"),
        (r"\bintegration\b", "integration"),
        (r"\borchestration\b", "orchestration"),
        (r"\bmigration\b", "migration"),
    ),
    "repo_review": (
        (r"\brepo(?:sitory)?\b", "repository"),
        (r"\bcode review\b", "code review"),
        (r"\baudit\b", "audit"),
        (r"\bcodebase\b", "codebase"),
        (r"\bwhole project\b", "whole project"),
        (r"\bmany files\b", "many files"),
    ),
    "research": (
        (r"\bresearch\b", "research"),
        (r"\bcompare\b", "compare"),
        (r"\binvestigate\b", "investigate"),
        (r"\blatest\b", "latest"),
        (r"\bbenchmarks?\b", "benchmark"),
        (r"\bevaluate\b", "evaluate"),
        (r"\banaly[sz]e\b", "analyze"),
        (r"\bsources?\b", "sources"),
    ),
    "automation": (
        (r"\bautomation\b", "automation"),
        (r"\bagentic\b", "agentic"),
        (r"\bagents?\b", "agent"),
        (r"\bworkflow\b", "workflow"),
        (r"\bscheduled\b", "scheduled"),
        (r"\bcron\b", "cron"),
        (r"\bmcp\b", "mcp"),
        (r"\bbot\b", "bot"),
        (r"\bautonomous\b", "autonomous"),
    ),
    "documents": (
        (r"\bdocument\b", "document"),
        (r"\bdocx\b", "docx"),
        (r"\bpdf\b", "pdf"),
        (r"\breport\b", "report"),
        (r"\bemail\b", "email"),
        (r"\bproposal\b", "proposal"),
    ),
    "spreadsheets": (
        (r"\bexcel\b", "excel"),
        (r"\bxlsx\b", "xlsx"),
        (r"\bspreadsheet\b", "spreadsheet"),
        (r"\bestimate\b", "estimate"),
        (r"\btakeoff\b", "takeoff"),
        (r"\bquantity\b", "quantity"),
    ),
}

# Backward-compatible name for callers that imported the old constant.
CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    category: tuple(pattern for pattern, _ in rules)
    for category, rules in CATEGORY_RULES.items()
}

CATEGORY_DIMENSION_WEIGHTS: dict[str, dict[str, float]] = {
    "implementation": {"coding": 1.1, "reasoning": 0.2, "agentic": 0.2},
    "debugging": {"coding": 0.8, "reasoning": 0.9, "ambiguity": 0.4},
    "architecture": {
        "coding": 0.5,
        "reasoning": 1.0,
        "agentic": 0.4,
        "ambiguity": 0.5,
        "breadth": 0.8,
    },
    "repo_review": {
        "coding": 0.6,
        "reasoning": 0.7,
        "agentic": 0.5,
        "breadth": 1.0,
        "parallelism": 0.7,
    },
    "research": {
        "reasoning": 1.0,
        "ambiguity": 0.4,
        "breadth": 0.5,
        "parallelism": 0.3,
    },
    "automation": {"coding": 0.3, "agentic": 1.0, "parallelism": 0.4},
    "documents": {"reasoning": 0.2},
    "spreadsheets": {"coding": 0.2, "reasoning": 0.7},
}

DIMENSION_RULES: dict[str, tuple[tuple[str, float, str], ...]] = {
    "coding": (
        (r"\b(write|modify|edit)\s+(?:the\s+)?code\b", 0.7, "explicit code change"),
        (r"\b(add|update)\s+(?:a\s+|the\s+)?tests?\b", 0.5, "test change"),
        (r"\b(api|endpoint|schema|sql|function|class)\b", 0.5, "code artifact"),
        (r"\b(fix|debug|refactor|implement)\b", 0.5, "code change verb"),
    ),
    "reasoning": (
        (r"\broot cause\b", 1.0, "root-cause analysis"),
        (r"\b(diagnose|reason about|trade[- ]?offs?)\b", 0.9, "diagnostic reasoning"),
        (r"\b(compare|evaluate|reconcile|verify|validate)\b", 0.7, "comparison/verification"),
        (r"\b(investigate|analy[sz]e|audit)\b", 0.8, "investigative reasoning"),
        (r"\bwhy\b", 0.4, "why-question"),
    ),
    "agentic": (
        (r"\b(end[- ]to[- ]end|from scratch)\b", 0.9, "end-to-end execution"),
        (r"\b(autonomous|overnight|long[- ]running)\b", 1.2, "long-running autonomy"),
        (r"\b(many|multiple)\s+steps\b", 0.9, "multi-step execution"),
        (r"\b(run|execute)\s+(?:the\s+)?tests?\b", 0.5, "execute tests"),
        (r"\b(open|create)\s+(?:a\s+)?(?:pull request|pr)\b", 0.7, "pull-request action"),
        (r"\b(deploy|publish|release)\b", 0.7, "delivery action"),
    ),
    "ambiguity": (
        (r"\b(unknown|unclear|uncertain)\b", 1.1, "explicit uncertainty"),
        (r"\bfigure out\b", 1.0, "figure-out request"),
        (r"\broot cause\b", 1.1, "unknown root cause"),
        (r"\bopen[- ]ended\b", 1.0, "open-ended task"),
        (r"\b(best approach|best way|what is wrong|why is)\b", 0.8, "solution uncertainty"),
    ),
    "breadth": (
        (r"\b(all|whole|entire|every)\b", 1.1, "whole-scope language"),
        (r"\b(repo[- ]wide|codebase[- ]wide|cross[- ]cutting)\b", 1.2, "cross-cutting scope"),
        (r"\b(hundreds?|dozens?)\s+(?:of\s+)?(?:files|modules|records)\b", 1.3, "large item count"),
        (r"\b(multiple|many)\s+(?:files|modules|services|systems|repos|repositories)\b", 1.0, "multi-component scope"),
        (r"\bmulti[- ]repo\b", 1.2, "multi-repository scope"),
    ),
    "parallelism": (
        (r"\bin parallel\b", 1.2, "explicit parallel work"),
        (r"\bindependent(?:ly)?\b", 0.7, "independent workstreams"),
        (r"\b(multiple|many)\s+(?:files|modules|services|sources|options)\b", 0.8, "parallelizable components"),
        (r"\bacross\s+(?:the\s+)?(?:repo|repository|codebase|modules|services|sources)\b", 0.8, "cross-component work"),
        (r"\b(compare|benchmark)\s+(?:multiple|several|many|different)\b", 0.7, "parallel comparison"),
    ),
}

SIMPLICITY_RULES: tuple[tuple[str, dict[str, float], str], ...] = (
    (
        r"\b(typo|spelling|punctuation)\b",
        {
            "reasoning": -0.8,
            "agentic": -0.8,
            "ambiguity": -0.9,
            "breadth": -0.8,
            "parallelism": -0.8,
        },
        "tiny textual change",
    ),
    (
        r"\b(one|single)\s+(?:file|line|field|value)\b",
        {
            "agentic": -0.5,
            "ambiguity": -0.4,
            "breadth": -0.8,
            "parallelism": -0.8,
        },
        "single-item scope",
    ),
    (
        r"\b(simple|small|tiny|quick|straightforward)\b",
        {
            "reasoning": -0.3,
            "agentic": -0.4,
            "ambiguity": -0.4,
            "breadth": -0.3,
        },
        "explicitly simple task",
    ),
)

ACTION_RE = re.compile(
    r"\b(implement|fix|debug|audit|investigate|compare|research|update|add|remove|"
    r"write|create|build|run|test|verify|validate|deploy|publish|refactor|migrate)\b",
    flags=re.IGNORECASE,
)

_NEGATION_RE = re.compile(
    r"\b(?:do not|don't|dont|without|avoid(?:ing)?|no need to)\b",
    flags=re.IGNORECASE,
)

_DIMENSIONS = ("coding", "reasoning", "agentic", "ambiguity", "breadth", "parallelism")


def _clamp(value: float) -> float:
    return max(1.0, min(5.0, value))


def _text_from_chatgpt_node(node: dict[str, Any]) -> str:
    message = node.get("message") or {}
    content = message.get("content") or {}
    parts = content.get("parts") or []
    return " ".join(part for part in parts if isinstance(part, str))


def _is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 80) : start]
    clause = re.split(r"[.;:!?]\s*", prefix)[-1]
    return bool(_NEGATION_RE.search(clause))


def _matched_labels(text: str, rules: tuple[tuple[str, str], ...]) -> list[str]:
    labels: list[str] = []
    for pattern, label in rules:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if _is_negated(text, match.start()):
                continue
            labels.append(label)
            break
    return labels


def _categories_for_text(text: str) -> set[str]:
    return {
        category
        for category, rules in CATEGORY_RULES.items()
        if _matched_labels(text, rules)
    }


def _profile_text(
    text: str,
) -> tuple[dict[str, list[str]], Counter[str], dict[str, list[str]]]:
    categories = {
        category: labels
        for category, rules in CATEGORY_RULES.items()
        if (labels := _matched_labels(text, rules))
    }
    dims: Counter[str] = Counter({name: 0.0 for name in _DIMENSIONS})
    signals: dict[str, list[str]] = {name: [] for name in _DIMENSIONS}

    for category in categories:
        for dimension, weight in CATEGORY_DIMENSION_WEIGHTS.get(category, {}).items():
            dims[dimension] += weight
            signals[dimension].append(f"category:{category}")

    for dimension, rules in DIMENSION_RULES.items():
        for pattern, weight, label in rules:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                if _is_negated(text, match.start()):
                    continue
                dims[dimension] += weight
                signals[dimension].append(label)
                break

    for pattern, adjustments, label in SIMPLICITY_RULES:
        if not re.search(pattern, text, flags=re.IGNORECASE):
            continue
        for dimension, adjustment in adjustments.items():
            dims[dimension] += adjustment
            signals[dimension].append(label)

    action_count = len(ACTION_RE.findall(text))
    if action_count >= 3:
        dims["agentic"] += 0.7
        dims["reasoning"] += 0.3
        signals["agentic"].append("three-or-more requested actions")
        signals["reasoning"].append("multi-action coordination")
    if action_count >= 5:
        dims["agentic"] += 0.6
        dims["breadth"] += 0.3
        signals["agentic"].append("five-or-more requested actions")
        signals["breadth"].append("large action set")

    for dimension in _DIMENSIONS:
        dims[dimension] = max(0.0, min(4.5, dims[dimension]))
        signals[dimension] = list(dict.fromkeys(signals[dimension]))

    return categories, dims, signals


class ActivityAnalyzer:
    """Turn activity text into explainable overall and category workload profiles.

    The profiler is deterministic and provider-independent. It intentionally has
    no private ChatGPT-history API and makes no provider calls.
    """

    def from_texts(self, texts: Iterable[str]) -> WorkloadProfile:
        items = [text.strip() for text in texts if text and text.strip()]
        categories: Counter[str] = Counter()
        dims: Counter[str] = Counter({name: 0.0 for name in _DIMENSIONS})
        category_signals: dict[str, list[str]] = {}
        dimension_signals: dict[str, list[str]] = {name: [] for name in _DIMENSIONS}
        evidence: list[str] = []

        for text in items:
            matched_categories, item_dims, item_signals = _profile_text(text)
            for category, labels in matched_categories.items():
                categories[category] += 1
                category_signals.setdefault(category, []).extend(labels)
            if matched_categories:
                evidence.append(text[:180].replace("\n", " "))
            for dimension in _DIMENSIONS:
                dims[dimension] += item_dims[dimension]
                dimension_signals[dimension].extend(item_signals[dimension])

        count = max(1, len(items))
        scale = max(1.0, count**0.5)

        def dimension(name: str) -> float:
            return _clamp(1.0 + (dims[name] / scale))

        return WorkloadProfile(
            coding=dimension("coding"),
            reasoning=dimension("reasoning"),
            agentic=dimension("agentic"),
            ambiguity=dimension("ambiguity"),
            breadth=dimension("breadth"),
            parallelism=dimension("parallelism"),
            latency_sensitivity=3.0,
            cost_sensitivity=3.0,
            volume=_clamp(1.0 + count / 20.0),
            categories=dict(categories),
            activity_count=len(items),
            evidence=evidence[:12],
            category_signals={
                key: list(dict.fromkeys(values))
                for key, values in category_signals.items()
            },
            dimension_signals={
                key: list(dict.fromkeys(values))[:12]
                for key, values in dimension_signals.items()
                if values
            },
        )

    def category_profiles_from_texts(
        self,
        texts: Iterable[str],
    ) -> dict[str, WorkloadProfile]:
        items = [text.strip() for text in texts if text and text.strip()]
        grouped: dict[str, list[str]] = {category: [] for category in CATEGORY_RULES}
        for text in items:
            for category in _categories_for_text(text):
                grouped[category].append(text)

        profiles: dict[str, WorkloadProfile] = {}
        for category, category_texts in grouped.items():
            if not category_texts:
                continue
            profile = self.from_texts(category_texts)
            profile.categories = {category: len(category_texts)}
            profile.category_signals = {
                category: profile.category_signals.get(category, [])
            }
            profiles[category] = profile
        return profiles

    @staticmethod
    def texts_from_generic_json(path: str | Path) -> list[str]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            records = data.get("activities", data.get("items", []))
        elif isinstance(data, list):
            records = data
        else:
            raise ValueError("Activity JSON must be a list or object")
        texts: list[str] = []
        for record in records:
            if isinstance(record, str):
                texts.append(record)
            elif isinstance(record, dict):
                text = " ".join(
                    str(record.get(key, ""))
                    for key in ("title", "text", "body", "action")
                )
                if text.strip():
                    texts.append(text)
        return texts

    @staticmethod
    def texts_from_chatgpt_export(path: str | Path) -> list[str]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        conversations = data if isinstance(data, list) else data.get("conversations", [])
        texts: list[str] = []
        for conversation in conversations:
            if not isinstance(conversation, dict):
                continue
            title = conversation.get("title")
            if isinstance(title, str):
                texts.append(title)
            mapping = conversation.get("mapping") or {}
            if isinstance(mapping, dict):
                for node in mapping.values():
                    if not isinstance(node, dict):
                        continue
                    message = node.get("message") or {}
                    author = (message.get("author") or {}).get("role")
                    if author == "user":
                        text = _text_from_chatgpt_node(node)
                        if text:
                            texts.append(text)
        return texts

    @staticmethod
    def texts_from_github_events(events: list[dict[str, Any]]) -> list[str]:
        texts: list[str] = []
        for event in events:
            repo = (event.get("repo") or {}).get("name", "")
            event_type = event.get("type", "")
            payload = event.get("payload") or {}
            fragments = [str(event_type), str(repo)]
            for key in ("action", "ref_type", "description"):
                if payload.get(key):
                    fragments.append(str(payload[key]))
            commits = payload.get("commits") or []
            for commit in commits[:20]:
                if isinstance(commit, dict) and commit.get("message"):
                    fragments.append(str(commit["message"]))
            texts.append(" ".join(fragments))
        return texts

    def from_generic_json(self, path: str | Path) -> WorkloadProfile:
        return self.from_texts(self.texts_from_generic_json(path))

    def from_chatgpt_export(self, path: str | Path) -> WorkloadProfile:
        return self.from_texts(self.texts_from_chatgpt_export(path))

    def from_github_events(self, events: list[dict[str, Any]]) -> WorkloadProfile:
        return self.from_texts(self.texts_from_github_events(events))

    @staticmethod
    def fetch_github_public_events(
        username: str,
        token: str | None = None,
    ) -> list[dict[str, Any]]:
        request = urllib.request.Request(
            f"https://api.github.com/users/{username}/events?per_page=100",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": (
                    "ai-model-advisor/0.9 "
                    "(+https://github.com/taiduc1302/ai-model-advisor)"
                ),
            },
        )
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not isinstance(data, list):
            raise ValueError("Unexpected GitHub events response")
        return data
