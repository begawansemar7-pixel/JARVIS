import json

import pytest

from knowledge.config import DEFAULT_CONFIG_PATH, load_config, parse_config
from knowledge.private_brain import (
    AccessContext,
    Classification,
    ConfidentialKnowledgePolicy,
    KnowledgeDocument,
    can_read,
)


def raw_config():
    return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


def test_repository_config_loads():
    cfg = load_config()
    assert cfg.max_cloud_classification is Classification.CONFIDENTIAL
    assert cfg.private_runtime_required_for == {Classification.SECRET, Classification.TOP_SECRET}
    assert cfg.log_access_decisions is True
    assert cfg.principal.subject == "owner"


def test_mismatched_levels_are_rejected():
    raw = raw_config()
    raw["classification_levels"]["SECRET"] = 1
    with pytest.raises(ValueError):
        parse_config(raw)


def test_content_logging_cannot_be_enabled():
    raw = raw_config()
    raw["log_content"] = True
    with pytest.raises(ValueError):
        parse_config(raw)


def test_unknown_classification_label_is_rejected():
    raw = raw_config()
    raw["max_cloud_classification"] = "SUPER_PUBLIC"
    with pytest.raises(ValueError):
        parse_config(raw)


def test_policy_follows_config(tmp_path):
    raw = raw_config()
    raw["max_cloud_classification"] = "INTERNAL"
    policy = ConfidentialKnowledgePolicy.from_config(parse_config(raw, tmp_path))
    doc = KnowledgeDocument("d", "t", Classification.CONFIDENTIAL, "owner")
    assert policy.require_private_runtime(doc)


def test_role_match_flag_is_honoured():
    doc = KnowledgeDocument("d", "t", Classification.INTERNAL, "owner", frozenset({"Board"}))
    ctx = AccessContext("u", frozenset({"Analyst"}), Classification.SECRET)
    assert not can_read(doc, ctx)
    assert can_read(doc, ctx, require_role_match=False)


def test_relative_storage_paths_resolve_against_base(tmp_path):
    cfg = parse_config(raw_config(), tmp_path)
    assert cfg.vault_dir == tmp_path / "memory/private_brain/vault"
