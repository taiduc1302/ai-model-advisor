# UX/accessibility audit — 2026-11-18

## Scope and source
- Baseline: `main` at `7a8056bad3dbd76ec5c6ea3592c47c3140cd1743`.
- Existing draft PR #23 (`ux/design-library-decision-compare-20261112`) remains separate; this branch does not cherry-pick or edit it. Re-test both sets of changes if they are later combined.
- Design ideas only: `taiduc1302/design-reference-library` (original components, accessible decision matrix, status/empty/error treatment, provenance); **no files were changed in that repository**.
- Accessibility research: `ChanMeng666/a11y-loop`, MIT license (2026 Chan Meng). Package 0.4.1 requires Node >=20 and depends on `@axe-core/playwright 4.14.0`, `axe-core 4.14.0` (MPL-2.0), `culori ^4.0.2` (MIT), `playwright 1.64.1` (Apache-2.0), `tabbable ^6.5.0` (MIT); optional MCP server and zod. Its CI action and package were **not installed or executed**. We apply its audit/fix/re-audit methodology only.

## Findings from existing `main`
1. **Confirmed in local Chromium:** `#results.results {display:grid}` overrode the HTML `hidden` state. Empty results, unpopulated cards and feedback controls were visible before a task was submitted. Fixed with explicit `[hidden]{display:none!important}`.
2. **Contrast calculation:** small secondary labels including `.nav-heading` (~4.0:1), `.optional` (~3.9:1), `.input-bottom` (~4.25:1), footer (~4.0:1), textarea placeholder (~4.15:1) were below 4.5:1 for normal text. Improved without replacing the theme.
3. **Keyboard/announcement:** no skip link or intentional focus destination after asynchronously showing a recommendation; results previously scrolled visually but focus was not moved to them. Added skip link, focusable heading, request status and error focus.
4. **Forced colors:** selected priority chip had no visible selection outline. Added system Highlight outline.
5. Existing submit label was fully replaced while loading, rather than updating its text. Preserved the native button and a stable text label. Loading/error/results states now appear explicitly.

The model registry, recommendation/feedback APIs, scoring and persistence code were not modified. The interface remains a deliberately dark theme in both system color schemes; a separate light theme was not implemented or claimed.

## Acceptance target and keyboard contract
- Target: WCAG 2.2 AA **where verifiable**, not a certification.
- Native radio group: Tab into group, arrow keys switch options. Native selects, textarea, buttons, form and details/summary retain browser behavior.
- Skip link: first Tab, Enter moves focus to main.
- Invalid submit: field receives focus with `aria-invalid=true`; error is announced and associated through `aria-describedby`.
- Async submit: existing polite live region announces progress; results focus moves to the primary heading; failures focus the visible error.
- Results must be hidden until data exists, and hidden while a new request runs. Feedback must not store task text.

## Evidence actually executed in isolated Chromium
Source-derived static HTML, CSS and JS were loaded in Chromium with synthetic responses, **not** from the production server. The following viewport checks were run in Chromium: 320, 390, 768, 1440px. At each width, the initial hidden state, keyboard skip navigation, no horizontal page scroll, empty validation, loading, result focus, request error, feedback error and success were exercised. Reduced-motion result scrolling was checked; forced-colors priority selection and 320px system-light rendering were checked. The initial failure and corrected behavior were captured as screenshots in the execution workspace.

Locally executed:
- `python -m pytest -q tests/test_web_accessibility_contract.py` — **4 passed** (source-contract tests; not UI screenshots).
- `node --check src/ai_model_advisor/web/app.js` — passed on local source-equivalent JS.
- Chromium isolated smoke suite — 320/390/768/1440 passed, including synthetic API state changes.
- Calculated after-fix text contrast: nav heading 6.86, optional 6.41, counter 6.08, footer 7.15, placeholder 6.45 (all ratios :1, selected pairs only).

Two runnable files are included in this branch:
- `tests/test_web_accessibility_contract.py` — pure Python test (no network or additional dependencies).
- `tools/check_web_a11y_offline.py` — opt-in Chromium/Playwright smoke runner using already installed dependencies. **Do not claim the exact committed script was executed until independently re-run from a full checkout.** Chromium was exercised with a locally developed equivalent workflow.

## Outstanding gates before merge
- Full `pytest -q` of the actual integrated checkout, lint (`ruff check`) and packaged `ai-model-advisor-web` server tests.
- Real HTTP/local-host, CSP, host/origin restrictions, `/api/meta`, `/api/decide` and `/api/feedback` regression after packaging. This agent's headless Chromium blocked localhost navigation with `ERR_BLOCKED_BY_ADMINISTRATOR`.
- Run the **exact committed** offline script and review screenshot diffs from the full checkout.
- Accessible-name/contrast audits in actual rendered success/error states (ideally axe-core), 200%/400% zoom and manual screen-reader inspection.
- Windows/Edge physical application launch, keyboard verification and feedback persistence.
- Rebase and rerun QA if PR #23 is merged or changes first.

**Status: review only — do not merge.** GitHub Actions should not be used for QA; tests are to be invoked manually/offline. No provider calls or production data were used.
