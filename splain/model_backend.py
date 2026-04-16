"""Ollama-backed explanation provider."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib import error, request

from splain.formatter import UNKNOWN_FLAG_MESSAGE
from splain.parser import ParsedCommand, ParsedFlag


PROMPT = """You are an expert Unix/Linux shell instructor.
Explain a command for a beginner.
Return JSON only with this schema:
{
  "description": "overall command description",
  "warning": "optional safety warning or null",
  "summary": "one-line plain English summary",
  "flags": [
    {"token": "-a", "explanation": "what it does", "value": "optional attached value or null"}
  ],
  "arguments": [
    {"value": "token", "explanation": "what it represents"}
  ],
  "suggestions": ["optional", "similar", "commands"]
}

Rules:
- Keep wording concise and beginner-friendly.
- Prefer short sentences and compact explanations.
- Explain known flags clearly.
- If a flag is unknown, explanation must be exactly: "Unknown flag, may be system-specific or uncommon."
- Warn for destructive commands like rm, chmod, chown, dd, mkfs, sudo, or shell redirection that overwrites files.
- Preserve the exact flag tokens and argument values from the input when possible.
"""

DEFAULT_OLLAMA_MODEL = "llama3.2:1b"


@dataclass
class ModelConfig:
    model: str | None = None
    api_base: str | None = None


class ModelBackendError(RuntimeError):
    """Raised when the model backend cannot provide an explanation."""


def build_backend(config: ModelConfig) -> "BaseModelBackend":
    return OllamaBackend(config)


class BaseModelBackend:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def explain(self, raw_command: str, base_command: str, flags: list[ParsedFlag], arguments: list[str]) -> ParsedCommand:
        raise NotImplementedError


class OllamaBackend(BaseModelBackend):
    def explain(self, raw_command: str, base_command: str, flags: list[ParsedFlag], arguments: list[str]) -> ParsedCommand:
        payload = {
            "model": self.config.model or DEFAULT_OLLAMA_MODEL,
            "stream": False,
            "format": "json",
            "keep_alive": "10m",
            "options": {
                "temperature": 0,
                "top_p": 0.9,
                "num_ctx": 2048,
                "num_predict": 280,
            },
            "messages": [
                {"role": "system", "content": PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "raw_command": raw_command,
                            "base_command": base_command,
                            "flags": [
                                {"token": flag.token, "value": flag.value}
                                for flag in flags
                            ],
                            "arguments": arguments,
                        },
                        separators=(",", ":"),
                    ),
                },
            ],
        }

        api_base = self.config.api_base or "http://127.0.0.1:11434"
        response_json = _post_json(
            f"{api_base.rstrip('/')}/api/chat",
            payload,
            headers={"Content-Type": "application/json"},
        )
        content = response_json["message"]["content"]
        return _build_result(raw_command, base_command, flags, arguments, content)


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=18) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise ModelBackendError(
            f"Unable to reach Ollama at {url}: {exc}. Start Ollama and pull '{payload.get('model', DEFAULT_OLLAMA_MODEL)}'."
        ) from exc
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ModelBackendError(f"Ollama returned HTTP {exc.code}: {detail}") from exc


def _build_result(
    raw_command: str,
    base_command: str,
    parsed_flags: list[ParsedFlag],
    parsed_arguments: list[str],
    model_text: str,
) -> ParsedCommand:
    try:
        payload = json.loads(model_text)
    except json.JSONDecodeError as exc:
        raise ModelBackendError("Model returned invalid JSON.") from exc

    flag_lookup = {flag.token: flag for flag in parsed_flags}
    flags: list[ParsedFlag] = []
    for item in payload.get("flags", []):
        token = item.get("token", "")
        original = flag_lookup.get(token)
        flags.append(
            ParsedFlag(
                token=token or (original.token if original else ""),
                value=item.get("value", original.value if original else None),
                explanation=item.get("explanation") or UNKNOWN_FLAG_MESSAGE,
                known=(item.get("explanation") or "") != UNKNOWN_FLAG_MESSAGE,
            )
        )

    if not flags:
        flags = [
            ParsedFlag(
                token=flag.token,
                value=flag.value,
                explanation=UNKNOWN_FLAG_MESSAGE,
                known=False,
            )
            for flag in parsed_flags
        ]

    argument_values = []
    argument_explanations = []
    for item in payload.get("arguments", []):
        argument_values.append(item.get("value", ""))
        argument_explanations.append(item.get("explanation", "Command argument."))

    if not argument_values:
        argument_values = parsed_arguments
        argument_explanations = ["Command argument." for _ in parsed_arguments]

    return ParsedCommand(
        raw=raw_command,
        command=base_command,
        description=payload.get("description", f"Explain what '{base_command}' does."),
        flags=flags,
        arguments=argument_values,
        argument_explanations=argument_explanations,
        summary=payload.get("summary", f"This command runs '{base_command}'."),
        warning=payload.get("warning"),
        suggestions=payload.get("suggestions", []),
    )
