"""Local prompt reference loading for governed agent invocations."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_ROOT = ROOT / "prompts"
_PROMPT_REFERENCE_PATTERN = re.compile(r"^prompts/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.md$")
_PROMPT_HASH_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


class PromptReferenceError(RuntimeError):
    """Raised when an approved prompt reference cannot be loaded or verified."""

    def __init__(
        self,
        *,
        prompt_reference: str,
        expected_hash: str,
        reason: str,
        actual_hash: str | None = None,
    ) -> None:
        self.prompt_reference = prompt_reference
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        self.reason = reason
        super().__init__(f"Prompt reference {prompt_reference!r} could not be loaded: {reason}")


@dataclass(frozen=True)
class LoadedPrompt:
    """Prompt content loaded from an approved local reference."""

    reference: str
    expected_hash: str
    content_hash: str
    content: str

    @property
    def metadata(self) -> dict[str, str | bool]:
        return {
            "prompt.reference": self.reference,
            "prompt.hash": self.expected_hash,
            "prompt.content_hash": self.content_hash,
            "prompt.hash_verified": True,
            "prompt.message_role": "system",
        }


def load_registered_prompt(prompt_reference: str, expected_hash: str) -> LoadedPrompt:
    """Load and verify a repo-local prompt reference from the agent registry."""

    prompt_path = _resolve_prompt_path(prompt_reference, expected_hash)
    if not _PROMPT_HASH_PATTERN.fullmatch(expected_hash):
        raise PromptReferenceError(
            prompt_reference=prompt_reference,
            expected_hash=expected_hash,
            reason="invalid_expected_hash",
        )
    try:
        prompt_bytes = prompt_path.read_bytes()
    except FileNotFoundError as exc:
        raise PromptReferenceError(
            prompt_reference=prompt_reference,
            expected_hash=expected_hash,
            reason="prompt_not_found",
        ) from exc

    content_hash = "sha256:" + hashlib.sha256(prompt_bytes).hexdigest()
    if content_hash != expected_hash:
        raise PromptReferenceError(
            prompt_reference=prompt_reference,
            expected_hash=expected_hash,
            actual_hash=content_hash,
            reason="prompt_hash_mismatch",
        )

    try:
        content = prompt_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromptReferenceError(
            prompt_reference=prompt_reference,
            expected_hash=expected_hash,
            actual_hash=content_hash,
            reason="prompt_not_utf8",
        ) from exc
    if not content.strip():
        raise PromptReferenceError(
            prompt_reference=prompt_reference,
            expected_hash=expected_hash,
            actual_hash=content_hash,
            reason="prompt_empty",
        )

    return LoadedPrompt(
        reference=prompt_reference,
        expected_hash=expected_hash,
        content_hash=content_hash,
        content=content,
    )


def _resolve_prompt_path(prompt_reference: str, expected_hash: str) -> Path:
    if not _PROMPT_REFERENCE_PATTERN.fullmatch(prompt_reference):
        raise PromptReferenceError(
            prompt_reference=prompt_reference,
            expected_hash=expected_hash,
            reason="invalid_prompt_reference",
        )
    relative = Path(prompt_reference)
    prompt_path = (ROOT / relative).resolve()
    try:
        prompt_path.relative_to(PROMPTS_ROOT.resolve())
    except ValueError as exc:
        raise PromptReferenceError(
            prompt_reference=prompt_reference,
            expected_hash=expected_hash,
            reason="prompt_outside_prompt_root",
        ) from exc
    return prompt_path


__all__ = [
    "LoadedPrompt",
    "PromptReferenceError",
    "load_registered_prompt",
]
