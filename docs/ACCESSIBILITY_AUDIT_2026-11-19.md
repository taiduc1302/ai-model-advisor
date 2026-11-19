# Accessibility audit — 2026-11-19

## Scope and provenance

- Target: `taiduc1302/ai-model-advisor`, based on `main` at `7a8056bad3dbd76ec5c6ea3592c47c3140cd1743`.
- Existing draft PR #23 is separate and not altered. This branch changes UI accessibility only; no model routing, pricing, API code or data persistence was changed.
- Read-only design reference: `taiduc1302/design-reference-library` (`docs/PROJECT_HANDOFF.md` and `AGENTS.md`). No files copied or changed.
- Read-only accessibility methodology: `ChanMeng666/a11y-loop` 0.4.1. MIT license confirmed. Dependencies include Playwright 1.64.1, axe-core 4.14.0, @axe-core/playwright 4.14.0, culori, tabbable, with optional MCP peers. Not installed, executed or copied into the app; no new runtime dependencies.

## Confirmed defects in Chromium

1. `#results[hidden]` was visibly rendered on page load because `.results{display:grid}` overrode the native hidden attribute. Observed at 320, 390, 768 and 1440 px.
2. The optimization priority's radio input was visually suppressed with `opacity:0`; high-contrast rendering provided no native selection indicator.
3. After a successful recommendation, scroll moved to results but keyboard focus did not move with it, leaving focus context behind.
4. When a new request failed, a previous successful recommendation stayed visible, creating a misleading stale-results state.

## Changes

- Ensure `[hidden]` reliably suppresses components. Provide a distinct, accessible loading status and restore the empty state on request errors.
- Add keyboard skip-to-task navigation and focus the newly rendered recommendation heading.
- Restore native visible radio inputs under Windows high-contrast/forced colors.
- Add explicit focus style for numeric feedback controls and preserve existing local-only `/api/meta`, `/api/decide`, `/api/feedback` endpoints.
- Keep all dynamic data rendered through text nodes. No vendor calls.

## Tests actually performed

**Chromium real-rendered UI with exact `main` HTML/CSS/JS and synthetic in-memory `fetch` responses** (not HTTP end-to-end): baseline 18/25; after fixes 25/25. Scenarios included 320/390/768/1440 viewport, no document overflow, visibility of empty/results, forced colors radio display, form validation and focus, example insertion, async loading, successful recommendation, focus retention, feedback save failure and retry, feedback success, API failure and stale-result suppression, malformed payload error.

Additional Chromium interactive checks: skip link first Tab stop, Enter targets task, subsequent Tab reaches example control. Light/dark preference at 320 px showed no document overflow; reduced-motion and non-reduced settings also rendered. The app remains dark-themed in both preferences; a separate light theme was not introduced.

**Offline static contract checks:** `pytest -q tests/test_accessibility_ui_contract.py` on a staged copy of modified assets: 5 passed.

## Not tested / merge blockers

- True server-backed HTTP/browser end-to-end and Content Security Policy verification: this runtime's Chromium blocks `http://127.0.0.1` and `file://` navigation with `net::ERR_BLOCKED_BY_ADMINISTRATOR`.
- Complete Python project regression and installed-package smoke: the runtime could not clone the complete repository (`Could not resolve host: github.com`).
- Real Playwright + axe-core automated WCAG scan, screen-reader review and native Windows/Edge forced-colors regression. Forced-colors was tested by Chromium emulation only.
- End-to-end and accessibility checks of PR #23 together with these changes: PR #23 remains independent.

**Status: Draft; not approved for merge.** Do not misinterpret passing isolated Chromium tests as full QA or WCAG certification.
