from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_YAML = ROOT / "BIBLIOGRAPHY_SOURCES_FR.yaml"
OUTPUT_MD = ROOT / "BIBLIOGRAPHY_SOURCES_FR.md"


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


def normalize_class_id(source: dict[str, Any]) -> str:
    class_id = source.get("class_id")
    if class_id:
        return class_id
    niveau = source.get("niveau_source")
    mapping = {
        "normatif": "normative_recommandations",
        "pratique": "professionnelle_pratique_fr",
        "pedagogique": "pedagogique_enseignement_medecins",
    }
    return mapping.get(niveau, "unclassified")


def scan_topic_sources() -> tuple[dict[str, dict[str, Any]], dict[str, set[str]], dict[str, set[str]]]:
    bibliography: dict[str, dict[str, Any]] = {}
    usage_topics: dict[str, set[str]] = defaultdict(set)
    usage_paths: dict[str, set[str]] = defaultdict(set)

    for family in ("complications", "terrains", "signaux_transverses"):
        family_dir = ROOT / family
        if not family_dir.exists():
            continue
        for topic_dir in sorted(path for path in family_dir.iterdir() if path.is_dir()):
            sources_path = topic_dir / "sources.yaml"
            if not sources_path.exists():
                continue
            payload = load_yaml(sources_path) or {}
            topic_id = payload.get("topic_id", topic_dir.name)
            topic_type = payload.get("topic_type", family[:-1])
            for source in payload.get("sources", []):
                source_id = source["source_id"]
                bibliography[source_id] = {
                    "entry_id": source_id,
                    "title": source.get("title"),
                    "organisme": source.get("organisme"),
                    "class_id": normalize_class_id(source),
                    "niveau_source": source.get("niveau_source"),
                    "support_type": source.get("support_type"),
                    "url": source.get("url"),
                    "date_consultation": source.get("date_consultation"),
                    "scope": "topic_source",
                    "credibility_role": "bibliographic_primary",
                }
                usage_topics[source_id].add(f"{topic_type}:{topic_id}")
                usage_paths[source_id].add(
                    str(sources_path.relative_to(ROOT.parent.parent))
                )
    return bibliography, usage_topics, usage_paths


def merge_resource_catalog(
    bibliography: dict[str, dict[str, Any]],
    usage_topics: dict[str, set[str]],
    usage_paths: dict[str, set[str]],
) -> None:
    payload = load_yaml(ROOT / "source_resource_catalog.yaml") or {}
    for resource in payload.get("resources", []):
        resource_id = resource["resource_id"]
        current = bibliography.get(resource_id, {})
        bibliography[resource_id] = {
            "entry_id": resource_id,
            "title": resource.get("title", current.get("title")),
            "organisme": resource.get("organisme", current.get("organisme")),
            "class_id": resource.get("class_id", current.get("class_id")),
            "niveau_source": resource.get("niveau_source", current.get("niveau_source")),
            "support_type": resource.get("source_kind", current.get("support_type")),
            "url": resource.get("url", current.get("url")),
            "date_consultation": resource.get("date_consultation", current.get("date_consultation", "2026-04-01")),
            "scope": current.get("scope", "resource_catalog"),
            "credibility_role": "bibliographic_secondary" if resource_id not in usage_topics else current.get("credibility_role", "bibliographic_primary"),
            "notes": resource.get("notes"),
        }
        usage_paths[resource_id].add("kb/sources_officielles/source_resource_catalog.yaml")


def build_output() -> dict[str, Any]:
    bibliography, usage_topics, usage_paths = scan_topic_sources()
    merge_resource_catalog(bibliography, usage_topics, usage_paths)

    entries = []
    for entry_id in sorted(bibliography):
        entry = dict(bibliography[entry_id])
        entry["used_by_topics"] = sorted(usage_topics.get(entry_id, []))
        entry["declared_in"] = sorted(usage_paths.get(entry_id, []))
        entry["evidence_traceability"] = {
            "url_present": bool(entry.get("url")),
            "organisme_present": bool(entry.get("organisme")),
            "class_present": bool(entry.get("class_id")),
        }
        entry["usage_count"] = len(entry["used_by_topics"])
        entries.append(entry)

    counts_by_class: dict[str, int] = defaultdict(int)
    for entry in entries:
        counts_by_class[entry["class_id"]] += 1

    return {
        "version": "2026-04-01",
        "goal": "Bibliographie francaise traceable pour la KB clinique CHARLES",
        "counts": {
            "total_entries": len(entries),
            "by_class": dict(sorted(counts_by_class.items())),
        },
        "entries": entries,
    }


def build_markdown(data: dict[str, Any]) -> str:
    entries = data["entries"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[entry["class_id"]].append(entry)

    lines: list[str] = []
    lines.append("# Bibliographie Francaise KB CHARLES")
    lines.append("")
    lines.append("Date: 2026-04-01")
    lines.append("")
    lines.append(
        "Cette bibliographie centralise les sources francaises reliees a la KB clinique. "
        "Chaque entree garde son URL, son organisme, sa classe documentaire et les "
        "themes CHARLES qui l'utilisent."
    )
    lines.append("")
    lines.append("## Comptage")
    lines.append("")
    lines.append(f"- Total: `{data['counts']['total_entries']}`")
    for class_id, count in data["counts"]["by_class"].items():
        lines.append(f"- `{class_id}`: `{count}`")
    lines.append("")

    for class_id in (
        "normative_recommandations",
        "professionnelle_pratique_fr",
        "pedagogique_enseignement_medecins",
        "unclassified",
    ):
        class_entries = grouped.get(class_id)
        if not class_entries:
            continue
        lines.append(f"## {class_id}")
        lines.append("")
        for entry in class_entries:
            lines.append(f"### {entry['entry_id']}")
            lines.append("")
            lines.append(f"- Titre: {entry.get('title')}")
            lines.append(f"- Organisme: `{entry.get('organisme')}`")
            lines.append(f"- URL: {entry.get('url')}")
            lines.append(f"- Support: `{entry.get('support_type')}`")
            lines.append(f"- Usage KB: `{entry.get('usage_count')}`")
            if entry.get("used_by_topics"):
                lines.append("- Themes relies: " + ", ".join(f"`{topic}`" for topic in entry["used_by_topics"]))
            if entry.get("declared_in"):
                lines.append("- Declare dans: " + ", ".join(f"`{path}`" for path in entry["declared_in"]))
            if entry.get("notes"):
                lines.append(f"- Note: {entry['notes']}")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    data = build_output()
    dump_yaml(OUTPUT_YAML, data)
    OUTPUT_MD.write_text(build_markdown(data), encoding="utf-8")


if __name__ == "__main__":
    main()
