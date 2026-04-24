from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
RESOURCE_CATALOG_PATH = ROOT / "source_resource_catalog.yaml"
LANDSCAPE_PATH = ROOT / "complication_source_landscape.yaml"


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def dump_yaml(path: Path, data: Any) -> None:
    path.write_text(
        yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=False,
            width=1000,
        ),
        encoding="utf-8",
    )


def build_catalog_index() -> dict[str, dict[str, Any]]:
    catalog = load_yaml(RESOURCE_CATALOG_PATH) or {}
    resources = catalog.get("resources", [])
    return {resource["resource_id"]: resource for resource in resources}


def build_landscape_index() -> dict[str, dict[str, Any]]:
    landscape = load_yaml(LANDSCAPE_PATH) or {}
    complications = landscape.get("complications", [])
    return {item["complication_id"]: item for item in complications}


def infer_class_id(source: dict[str, Any]) -> str | None:
    if source.get("class_id"):
        return source["class_id"]
    niveau_source = source.get("niveau_source")
    mapping = {
        "normatif": "normative_recommandations",
        "pratique": "professionnelle_pratique_fr",
        "pedagogique": "pedagogique_enseignement_medecins",
    }
    return mapping.get(niveau_source)


def merge_source_index(
    local_sources: list[dict[str, Any]],
    catalog_index: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source in local_sources:
        source_copy = dict(source)
        source_copy["class_id"] = infer_class_id(source_copy)
        merged[source_copy["source_id"]] = source_copy
    for source_id, resource in catalog_index.items():
        if source_id not in merged:
            merged[source_id] = dict(resource)
    return merged


def enrich_facts_file(facts_path: Path, source_index: dict[str, dict[str, Any]]) -> None:
    if not facts_path.exists():
        return
    payload = load_yaml(facts_path) or {}
    changed = False
    for fact in payload.get("faits", []):
        source_ref = fact.get("source_ref")
        if not source_ref:
            continue
        source = source_index.get(source_ref)
        if not source:
            continue
        additions = {
            "source_title": source.get("title"),
            "source_url": source.get("url"),
            "source_organisme": source.get("organisme"),
            "source_class_id": infer_class_id(source),
            "source_support_type": source.get("support_type") or source.get("source_kind"),
        }
        for key, value in additions.items():
            if value is not None and fact.get(key) != value:
                fact[key] = value
                changed = True
    if changed:
        dump_yaml(facts_path, payload)


def enrich_complication_sources(
    sources_path: Path,
    landscape_entry: dict[str, Any] | None,
) -> None:
    payload = load_yaml(sources_path) or {}
    changed = False

    if landscape_entry:
        layers = landscape_entry.get("source_layers")
        notes = landscape_entry.get("notes", [])
        if payload.get("documentary_layers") != layers:
            payload["documentary_layers"] = layers
            changed = True
        if payload.get("documentary_notes") != notes:
            payload["documentary_notes"] = notes
            changed = True

    traceability = {
        "fact_link_fields": [
            "source_ref",
            "source_title",
            "source_url",
            "source_organisme",
            "source_class_id",
        ],
        "resource_catalog_ref": "kb/sources_officielles/source_resource_catalog.yaml",
        "landscape_ref": "kb/sources_officielles/complication_source_landscape.yaml",
    }
    if payload.get("traceability") != traceability:
        payload["traceability"] = traceability
        changed = True

    if changed:
        dump_yaml(sources_path, payload)


def enrich_generic_sources(sources_path: Path) -> None:
    payload = load_yaml(sources_path) or {}
    traceability = {
        "fact_link_fields": [
            "source_ref",
            "source_title",
            "source_url",
            "source_organisme",
            "source_class_id",
        ]
    }
    if payload.get("traceability") != traceability:
        payload["traceability"] = traceability
        dump_yaml(sources_path, payload)


def main() -> None:
    catalog_index = build_catalog_index()
    landscape_index = build_landscape_index()

    for family in ("complications", "terrains", "signaux_transverses"):
        base = ROOT / family
        if not base.exists():
            continue
        for topic_dir in sorted(path for path in base.iterdir() if path.is_dir()):
            sources_path = topic_dir / "sources.yaml"
            if not sources_path.exists():
                continue
            sources_payload = load_yaml(sources_path) or {}
            local_sources = sources_payload.get("sources", [])
            source_index = merge_source_index(local_sources, catalog_index)

            if family == "complications":
                enrich_complication_sources(
                    sources_path,
                    landscape_index.get(topic_dir.name),
                )
            else:
                enrich_generic_sources(sources_path)

            enrich_facts_file(topic_dir / "faits_source.yaml", source_index)


if __name__ == "__main__":
    main()
