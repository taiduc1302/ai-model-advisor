"""Standalone CLI entrypoint."""

from tools.ai_model_advisor.cli import build_parser, main

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
