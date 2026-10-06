# Current model registry

Registry snapshot: **2026-10-06**

The default recommendation pool contains only current/latest candidates. Older
but still useful models may remain in the registry with `status=previous` for
historical feedback compatibility; they are excluded from normal routing.

Current default candidates:

- OpenAI: GPT-6 Astra, GPT-6.1 Sol, GPT-6 Luna.
- Anthropic: Claude Fable 5.1, Claude Opus 5.5, Claude Sonnet 5.5, Claude Haiku 4.5.

Pricing, model IDs, context windows, output limits, and supported effort levels
come from official provider documentation. Capability values on the 1-5 scale
are Advisor heuristics for routing, not provider benchmarks.

The registry should be refreshed when official model catalogs or release notes
change materially. Personal feedback is retained by exact model ID and does not
silently transfer from an older model to its successor.
