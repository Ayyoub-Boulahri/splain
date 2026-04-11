"""Parsing helpers for shell commands."""

from __future__ import annotations

from dataclasses import dataclass, field
import shlex


@dataclass
class ParsedFlag:
    token: str
    value: str | None = None
    explanation: str | None = None
    known: bool = True


@dataclass
class ParsedCommand:
    raw: str
    command: str
    description: str
    flags: list[ParsedFlag] = field(default_factory=list)
    arguments: list[str] = field(default_factory=list)
    argument_explanations: list[str] = field(default_factory=list)
    summary: str = ""
    warning: str | None = None
    suggestions: list[str] = field(default_factory=list)


def tokenize(command_text: str) -> list[str]:
    """Split a shell command string like a shell would."""
    return shlex.split(command_text)


def parse_command(command_text: str) -> tuple[str, list[ParsedFlag], list[str]]:
    """Parse command text into a base command, flags, and positional arguments."""
    tokens = tokenize(command_text)
    if not tokens:
        raise ValueError("No command provided.")

    base_command = tokens[0]
    remaining = tokens[1:]
    return base_command, *_fallback_parse_tokens(remaining)


def _parse_long_flag(token: str) -> tuple[str, str | None]:
    if "=" in token:
        flag, value = token.split("=", 1)
        return flag, value
    return token, None


def _split_short_flags(token: str) -> list[ParsedFlag]:
    parts: list[ParsedFlag] = []
    body = token[1:]
    if body.isalpha():
        for char in body:
            parts.append(ParsedFlag(token=f"-{char}", known=False))
        return parts

    flag = f"-{body[0]}"
    value = body[1:] or None
    parts.append(ParsedFlag(token=flag, value=value, known=False))

    return parts


def _fallback_parse_tokens(tokens: list[str]) -> tuple[list[ParsedFlag], list[str]]:
    """Best-effort parse for unknown commands."""
    flags: list[ParsedFlag] = []
    arguments: list[str] = []
    for token in tokens:
        if token.startswith("-") and token != "-":
            if token.startswith("--"):
                flag, value = _parse_long_flag(token)
                flags.append(ParsedFlag(token=flag, value=value, known=False))
            elif len(token) > 2:
                flags.extend(_split_short_flags(token))
            else:
                flags.append(ParsedFlag(token=token, known=False))
        else:
            arguments.append(token)
    return flags, arguments
