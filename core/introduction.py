"""JARVIS self-introduction: who it works for and who created it.

Used in two places so the answer never drifts:
  * the [IDENTITY] block of the system prompt (answers "who are you?" any time)
  * the startup greeting (introduces itself when it is switched on)

"AI Employee" and the creator's name are proper terms: the model is told to keep
them verbatim while the rest of the sentence follows the user's language.
"""
from __future__ import annotations

CREATOR = "Ko Henri"
ROLE = "AI Employee"


def employee_title(user_name: str = "") -> str:
    user_name = (user_name or "").strip()
    return f"{ROLE} {user_name}" if user_name else ROLE


def identity_line(assistant_name: str, user_name: str = "") -> str:
    """Sentence for the system prompt's [IDENTITY] block."""
    owner = (user_name or "").strip() or "the user"
    return (
        f"You are {assistant_name}, the {ROLE} of {owner}, created by {CREATOR}. "
        f"When asked who you are, who you work for or who made you, say exactly that. "
        f"Keep the words '{ROLE}' and '{CREATOR}' unchanged in every language."
    )


def startup_introduction_clause(assistant_name: str, user_name: str = "") -> str:
    """Instruction appended to the startup greeting prompt."""
    return (
        f" Right after the greeting, introduce yourself in one short sentence as {assistant_name}, "
        f"{employee_title(user_name)}, created by {CREATOR} — keep '{ROLE}' and '{CREATOR}' "
        f"exactly as written, even when speaking another language."
    )


__all__ = ["CREATOR", "ROLE", "employee_title", "identity_line", "startup_introduction_clause"]
