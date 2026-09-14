from __future__ import annotations

from .models import SkillContext, SkillRecord, SkillResolution
from .registry import SkillRegistry


class SkillResolver:
    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def resolve(self, task: str, *, skill_name: str | None = None,
                context: SkillContext | None = None) -> SkillResolution:
        active = list(self.registry.all(active_only=True))
        if skill_name:
            exact = self.registry.get_active(skill_name)
            return SkillResolution(exact, (exact,) if exact else (), "explicit skill name")

        query = set(task.lower().split())
        scored: list[tuple[int, SkillRecord]] = []
        for record in active:
            trigger_tokens = set(" ".join(record.manifest.triggers).lower().split())
            score = len(query & trigger_tokens)
            if context:
                if record.manifest.category.lower() == str(context.metadata.get("category", "")).lower():
                    score += 10
                if set(record.manifest.requires_actions) <= set(context.available_actions):
                    score += 2
                if set(record.manifest.requires_plugins) <= set(context.available_plugins):
                    score += 2
            if score:
                scored.append((score, record))

        scored.sort(key=lambda item: (-item[0], item[1].manifest.name, item[1].manifest.version))
        candidates = tuple(record for _, record in scored)
        selected = candidates[0] if candidates else None
        return SkillResolution(selected, candidates, "trigger/category resolution")
