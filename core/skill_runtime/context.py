from .models import SkillContext


def build_context(task: str, *, inputs=None, session_id="", correlation_id="",
                  available_actions=None, available_plugins=None, metadata=None) -> SkillContext:
    return SkillContext(
        task=task,
        inputs=dict(inputs or {}),
        session_id=session_id,
        correlation_id=correlation_id,
        available_actions=frozenset(available_actions or ()),
        available_plugins=frozenset(available_plugins or ()),
        metadata=dict(metadata or {}),
    )
