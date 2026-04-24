from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
KB_SOURCES = ROOT / "kb" / "sources_officielles"
KB_ENGINE = ROOT / "kb" / "complication_engine"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_all_kb_yaml_files_parse() -> None:
    for base in (KB_SOURCES, KB_ENGINE):
        for path in base.rglob("*.yaml"):
            data = load_yaml(path)
            assert data is not None, f"{path} should parse"


def test_complication_facts_have_direct_traceability_fields() -> None:
    for path in (KB_SOURCES / "complications").rglob("faits_source.yaml"):
        payload = load_yaml(path)
        for fact in payload.get("faits", []):
            assert fact.get("source_ref"), f"{path}: missing source_ref"
            assert fact.get("source_title"), f"{path}: missing source_title for {fact.get('fact_id')}"
            assert fact.get("source_url"), f"{path}: missing source_url for {fact.get('fact_id')}"
            assert fact.get("source_organisme"), f"{path}: missing source_organisme for {fact.get('fact_id')}"
            assert fact.get("source_class_id"), f"{path}: missing source_class_id for {fact.get('fact_id')}"


def test_complication_sources_embed_documentary_layers() -> None:
    landscape = load_yaml(KB_SOURCES / "complication_source_landscape.yaml")
    landscape_index = {item["complication_id"]: item for item in landscape.get("complications", [])}

    for path in (KB_SOURCES / "complications").rglob("sources.yaml"):
        payload = load_yaml(path)
        complication_id = payload.get("topic_id")
        assert complication_id in landscape_index, f"{path}: no landscape entry"
        assert payload.get("documentary_layers"), f"{path}: documentary_layers missing"
        assert payload.get("traceability"), f"{path}: traceability section missing"


def test_bibliography_is_present_and_traceable() -> None:
    bibliography_path = KB_SOURCES / "BIBLIOGRAPHY_SOURCES_FR.yaml"
    payload = load_yaml(bibliography_path)
    assert payload.get("entries"), "bibliography should contain entries"
    for entry in payload["entries"]:
        assert entry.get("title"), f"{entry.get('entry_id')} missing title"
        assert entry.get("organisme"), f"{entry.get('entry_id')} missing organisme"
        assert entry.get("url"), f"{entry.get('entry_id')} missing url"
        assert entry.get("class_id"), f"{entry.get('entry_id')} missing class_id"


def test_discovery_tools_are_not_evidence_sources() -> None:
    payload = load_yaml(KB_SOURCES / "discovery_tools.yaml")
    tools = payload.get("tools", [])
    assert tools, "discovery tools should be declared"
    for tool in tools:
        assert tool.get("role") == "discovery_only"
        assert tool.get("url")
