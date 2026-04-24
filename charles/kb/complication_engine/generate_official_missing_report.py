from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = ROOT / "OFFICIAL_KB_MISSING_WITH_WITHOUT_WAVEFORMS.md"


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def classify_input(input_id: str) -> str:
    waveform_ids = {
        "capnography_shape",
        "capnography_presence",
        "capnography_or_bronchospasm_pattern",
        "etco2_trend_velocity",
        "etco2_sudden_drop",
    }
    if input_id in waveform_ids:
        return "waveform_plus"
    return "non_wave_or_context"


def format_items(items: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in items:
        lines.append(
            f"- `{item['label_fr']}` (`{item['input_id']}`): {item['why']} "
            f"[status: {item['current_status']}]"
        )
    return lines


def main() -> None:
    registry = load_yaml(ROOT / "complications_registry.yaml")
    required = load_yaml(ROOT / "official_required_inputs.yaml")

    req_index = {
        item["complication_id"]: item["official_required_inputs"]
        for item in required.get("complications", [])
    }

    lines: list[str] = []
    lines.append("# Manques KB Officielle Avec / Sans Waveforms")
    lines.append("")
    lines.append("Date: 2026-04-01")
    lines.append("")
    lines.append(
        "Ce rapport reste strictement sur la branche `sources officielles`. "
        "Il ne fusionne pas encore l'evidence VitalDB dans les conclusions."
    )
    lines.append("")
    lines.append("## Regle de lecture")
    lines.append("")
    lines.append("- `sans waveforms`: numeriques monitor, contexte clinique, labs, terrain")
    lines.append("- `avec waveforms`: morphologie capnographique ou signaux temporels manquants")
    lines.append("- `hors monitorage`: donnees cliniques, therapeutiques ou contextuelles qu'aucune waveform ne comblera seule")
    lines.append("")

    for complication in registry.get("complications", []):
        complication_id = complication["complication_id"]
        official = req_index.get(complication_id, {})
        required_items = official.get("required", [])
        useful_items = official.get("useful", [])

        waveform_required = [
            item for item in required_items if classify_input(item["input_id"]) == "waveform_plus"
        ]
        non_wave_required = [
            item for item in required_items if classify_input(item["input_id"]) != "waveform_plus"
        ]
        waveform_useful = [
            item for item in useful_items if classify_input(item["input_id"]) == "waveform_plus"
        ]
        non_wave_useful = [
            item for item in useful_items if classify_input(item["input_id"]) != "waveform_plus"
        ]

        still_missing_even_with_waveforms = [
            item
            for item in non_wave_required + non_wave_useful
            if item["current_status"] == "missing"
        ]
        helped_by_waveforms = [
            item
            for item in waveform_required + waveform_useful
            if item["current_status"] in {"missing", "partial"}
        ]

        lines.append(f"## {complication_id}")
        lines.append("")
        lines.append(
            f"- Famille: `{complication['family']}`"
        )
        lines.append(
            f"- No-wave cible dans le registry: `{str(complication['no_wave_ready']).lower()}`"
        )
        lines.append(
            f"- Waveforms utiles dans le registry: `{str(complication['wave_ready']).lower()}`"
        )
        lines.append("")
        lines.append("### Sans waveforms")
        lines.append("")
        if non_wave_required:
            lines.append("Inputs requis:")
            lines.extend(format_items(non_wave_required))
        if non_wave_useful:
            lines.append("Inputs utiles:")
            lines.extend(format_items(non_wave_useful))
        if not non_wave_required and not non_wave_useful:
            lines.append("- Aucun input non-wave recense")
        lines.append("")
        lines.append("### Apport potentiel des waveforms")
        lines.append("")
        if waveform_required or waveform_useful:
            if waveform_required:
                lines.append("Inputs requis dependants des waveforms:")
                lines.extend(format_items(waveform_required))
            if waveform_useful:
                lines.append("Inputs utiles dependants des waveforms:")
                lines.extend(format_items(waveform_useful))
        else:
            lines.append("- Cette complication est surtout contrainte par des donnees numeriques ou contextuelles.")
        lines.append("")
        lines.append("### Ce qui manque encore meme avec waveforms")
        lines.append("")
        if still_missing_even_with_waveforms:
            lines.extend(format_items(still_missing_even_with_waveforms))
        else:
            lines.append("- Rien de critique n'est marque `missing` hors branche waveform.")
        lines.append("")
        lines.append("### Ce que les waveforms peuvent reellement combler")
        lines.append("")
        if helped_by_waveforms:
            lines.extend(format_items(helped_by_waveforms))
        else:
            lines.append("- Peu de gain attendu uniquement par morphologie waveform.")
        lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
