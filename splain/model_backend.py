"""Model-backed explanation providers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
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
- Explain known flags clearly.
- If a flag is unknown, explanation must be exactly: "Unknown flag, may be system-specific or uncommon."
- Warn for destructive commands like rm, chmod, chown, dd, mkfs, sudo, or shell redirection that overwrites files.
- Preserve the exact flag tokens and argument values from the input when possible.
"""


@dataclass
class ModelConfig:
    provider: str
    model: str | None = None
    api_base: str | None = None


class ModelBackendError(RuntimeError):
    """Raised when the model backend cannot provide an explanation."""


def build_backend(config: ModelConfig) -> "BaseModelBackend":
    provider = config.provider.lower()
    if provider == "openai":
        return OpenAIBackend(config)
    if provider == "ollama":
        return OllamaBackend(config)
    if provider == "offline":
        return OfflineBackend(config)
    raise ModelBackendError(f"Unsupported provider: {config.provider}")


class BaseModelBackend:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def explain(self, raw_command: str, base_command: str, flags: list[ParsedFlag], arguments: list[str]) -> ParsedCommand:
        raise NotImplementedError


class OfflineBackend(BaseModelBackend):
    """Fallback mode when no model service is configured."""

    def explain(self, raw_command: str, base_command: str, flags: list[ParsedFlag], arguments: list[str]) -> ParsedCommand:
        return ParsedCommand(
            raw=raw_command,
            command=base_command,
            description=(
                "Model backend not configured. The command structure was parsed locally, "
                "but semantic explanations require an expert model provider."
            ),
            flags=[
                ParsedFlag(
                    token=flag.token,
                    value=flag.value,
                    explanation=UNKNOWN_FLAG_MESSAGE,
                    known=False,
                )
                for flag in flags
            ],
            arguments=arguments,
            argument_explanations=["Command argument." for _ in arguments],
            summary=f"This appears to run '{base_command}', but no expert model backend is configured.",
            suggestions=[],
        )


class OpenAIBackend(BaseModelBackend):
    def explain(self, raw_command: str, base_command: str, flags: list[ParsedFlag], arguments: list[str]) -> ParsedCommand:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ModelBackendError("OPENAI_API_KEY is not set.")

        payload = {
            "model": self.config.model or os.environ.get("EXPLAIN_MODEL", "gpt-5.4-mini"),
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": PROMPT}]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "raw_command": raw_command,
                                    "base_command": base_command,
                                    "flags": [
                                        {"token": flag.token, "value": flag.value}
                                        for flag in flags
                                    ],
                                    "arguments": arguments,
                                },
                                indent=2,
                            ),
                        }
                    ],
                },
            ],
        }

        api_base = self.config.api_base or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        response_json = _post_json(
            f"{api_base.rstrip('/')}/responses",
            payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        content = _extract_openai_text(response_json)
        return _build_result(raw_command, base_command, flags, arguments, content)


class OllamaBackend(BaseModelBackend):
    def explain(self, raw_command: str, base_command: str, flags: list[ParsedFlag], arguments: list[str]) -> ParsedCommand:
        payload = {
            "model": self.config.model or os.environ.get("EXPLAIN_MODEL", "llama3.1"),
            "stream": False,
            "format": "json",
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
                        indent=2,
                    ),
                },
            ],
        }

        api_base = self.config.api_base or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
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
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise ModelBackendError(f"Unable to reach model provider at {url}: {exc}") from exc
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ModelBackendError(f"Model provider returned HTTP {exc.code}: {detail}") from exc


def _extract_openai_text(response_json: dict[str, Any]) -> str:
    output = response_json.get("output", [])
    texts: list[str] = []
    for item in output:
        for content_item in item.get("content", []):
            text = content_item.get("text")
            if text:
                texts.append(text)
    if texts:
        return "\n".join(texts)
    raise ModelBackendError("OpenAI response did not contain text output.")


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
