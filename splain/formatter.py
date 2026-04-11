"""Output formatting for explanations."""

from __future__ import annotations

import json

from splain.parser import ParsedCommand


UNKNOWN_FLAG_MESSAGE = "Unknown flag, may be system-specific or uncommon."


def format_text(result: ParsedCommand, detailed: bool = True) -> str:
    """Format the explanation as readable text."""
    lines: list[str] = [
        f"Command: {result.raw}",
        "",
        f"Description: {result.description}",
    ]

    if result.warning:
        lines.extend(["", result.warning])

    if result.flags:
        lines.extend(["", "Flags:"])
        for flag in result.flags:
            detail = flag.explanation or UNKNOWN_FLAG_MESSAGE
            if flag.value is not None and detailed:
                detail = f"{detail} Value: {flag.value}"
            lines.append(f"  - {flag.token} -> {detail}")

    if result.arguments:
        title = "Arguments:" if len(result.arguments) > 1 else "Argument:"
        lines.extend(["", title])
        for index, argument in enumerate(result.arguments):
            explanation = result.argument_explanations[index] if index < len(result.argument_explanations) else "Command argument."
            lines.append(f"  - {argument} -> {explanation}")

    if result.suggestions:
        lines.extend(["", f"Suggestions: {', '.join(result.suggestions)}"])

    lines.extend(["", f"Summary: {result.summary}"])
    return "\n".join(lines)


def format_json(result: ParsedCommand) -> str:
    """Format the explanation as JSON."""
    payload = {
        "command": result.raw,
        "base_command": result.command,
        "description": result.description,
        "warning": result.warning,
        "flags": [
            {
                "flag": flag.token,
                "value": flag.value,
                "known": flag.known,
                "explanation": flag.explanation or UNKNOWN_FLAG_MESSAGE,
            }
            for flag in result.flags
        ],
        "arguments": [
            {
                "value": argument,
                "explanation": result.argument_explanations[index] if index < len(result.argument_explanations) else "Command argument.",
            }
            for index, argument in enumerate(result.arguments)
        ],
        "summary": result.summary,
        "suggestions": result.suggestions,
    }
    return json.dumps(payload, indent=2)
