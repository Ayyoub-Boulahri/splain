"""CLI entry point for explain."""

from __future__ import annotations

import argparse
import os
import sys

from splain.formatter import format_json, format_text
from splain.model_backend import ModelBackendError, ModelConfig, build_backend
from splain.parser import parse_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="explain",
        description="Explain a shell command in beginner-friendly language.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--short",
        action="store_true",
        help="Use a shorter explanation.",
    )
    mode_group.add_argument(
        "--detailed",
        action="store_true",
        help="Use a more detailed explanation (default).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the explanation as JSON.",
    )
    parser.add_argument(
        "--provider",
        default=os.environ.get("EXPLAIN_PROVIDER", "offline"),
        choices=["openai", "ollama", "offline"],
        help="Explanation backend to use.",
    )
    parser.add_argument(
        "--model",
        help="Model name for the selected provider.",
    )
    parser.add_argument(
        "--api-base",
        help="Optional base URL for the selected provider.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        help='The shell command to explain, for example: "tar -xzvf file.tar.gz"',
    )
    return parser


def explain_command(command_text: str, provider: str, model: str | None, api_base: str | None):
    try:
        base_command, flags, arguments = parse_command(command_text)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    backend = build_backend(ModelConfig(provider=provider, model=model, api_base=api_base))
    return backend.explain(command_text, base_command, flags, arguments)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help(sys.stderr)
        return 2

    try:
        result = explain_command(args.command, provider=args.provider, model=args.model, api_base=args.api_base)
    except ModelBackendError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    detailed = not args.short

    if args.json:
        print(format_json(result))
    else:
        print(format_text(result, detailed=detailed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
