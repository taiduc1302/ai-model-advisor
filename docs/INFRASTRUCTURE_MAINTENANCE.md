# GitHub and deployment maintenance

## Deployment boundary

The application currently runs as a local-only, unauthenticated Python HTTP server.
It binds to 127.0.0.1 and stores optional user feedback in a local JSONL file.
It must not be deployed directly to a publicly reachable Vercel function: the authentication,
storage, and local-only security assumptions would be invalid.

The root vercel.json disables automatic Git deployments while there is no reviewed
serverless/public deployment. It does not repair prior failed deployment statuses,
delete the Vercel project, or guarantee a working public URL.

To disconnect the Vercel integration entirely, go to Vercel project ai-model-advisor,
Settings > Git > Connected Git Repository > Disconnect.
See https://vercel.com/docs/project-configuration/git-settings .

Before public hosting is re-enabled, implement authentication, secure persistent storage,
CSRF/origin protection appropriate to the host, a deployment-compatible HTTP adapter,
and integration testing against a live deployment.

## Model Registry Monitor

Monitor runs weekly rather than daily to reduce GitHub Actions minutes.
New unknown signals now create or update one human-review issue and generate an
Actions warning, summary, and artifact; no model is registered automatically.
The job only fails for actual scan, artifact, or issue-publication errors.
A source label by itself is NOT proof of a new public model.

## Branch hygiene

On 2026-11-02 there were 20 branches: main, historical feature branches,
and other docs/feat work. PR #18 (civil-ai-agent-kit) is open: protect its branch.

Enable GitHub Settings > General > Pull Requests > Automatically delete head branches.
Apply a main-branch ruleset requiring successful CI / core checks.

Past merged feature branches may be deleted only after matching the head to a
merged PR. Do not delete main, protected branches, open PR heads, or docs/feat branches
without review. The GitHub connector used for this audit cannot delete refs or
change repository administrative settings; an owner must apply those changes
from GitHub or the GitHub CLI.

## Verification checklist

- CI / core passes on main and on this infrastructure PR.
- New Vercel auto-builds do not start after the changed Git configuration is respected.
- Monitor maintains a stable review issue for unverified model names.
- Genuine monitor failures remain visible.
- No active work or unique branches are deleted.
