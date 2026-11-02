# Coding — controlled software changes

**Scope:** application code, tests, schemas, desktop automation scripts and connectors.

1. Record baseline SHA, active owner/branch, intended files, supported platform and exact acceptance criteria. Consult existing repository instructions before changing anything.
2. Classify change: **low** (docs/test fixture), **medium** (code inside tested boundary), **high** (auth, permissions, data migrations, dependencies, external effects, estimates or native automation). High-risk changes need explicit human approval.
3. Work in isolated, small commits; never force-push or overwrite another agent's work. If multiple contributors share a repo, coordinate on shared issue/board first.
4. Run targeted tests, negative controls, regression tests and packaging checks; run broader suite where feasible. For each: command, environment, exit code, PASS/FAIL/NOT RUN and artifact location.
5. If a check fails, retain a failing fixture or reproduction and investigate instead of deleting or weakening the test. No self-issued approval.
6. Use synthetic data in public CI; no production tokens, internal tender documents, employee information, or restricted codebooks.
7. Close with impact, changed files, observed test results, limitations, independent review status and rollback.

**Minimum gate:** relevant tests pass and diff is reviewed. If tests couldn't run, label `NOT RUN`; never imply coverage. Code review does not replace native-tool read-back for estimating workflows.
