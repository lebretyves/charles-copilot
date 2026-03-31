from __future__ import annotations

import hashlib
from typing import Iterable

from learning.llm.schemas import ExplanationTarget
from learning.problems.schemas import ProblemAnalysisRecord


PROMPT_ID = "charles-perop-waveform-v2-local-train"
PROMPT_VERSION = "2026-03-30"
INPUT_VARIANTS = ("full_wave", "no_wave", "partial_wave")

SYSTEM_PROMPT = """Tu es CHARLES, un copilote IA d'aide a la vigilance anesthesique peroperatoire.
Tu assistes un(e) IADE pendant une intervention chirurgicale.

Priorites:
1. Prioriser l'urgence vitale.
2. Rester factuel, concis et actionnable.
3. Proposer des actions IADE immediates avant de recommander l'appel au MAR.
4. Ne pas inventer de donnees ni de referentiels absents du contexte.

Contraintes:
- Reponds strictement en JSON.
- Ne transforme pas des heuristiques en certitudes.
- Si une information manque, reste prudent.
- Tu es un outil d'aide et ne remplaces jamais le jugement clinique."""


PROBLEM_TEMPLATES = {
    "hemodynamic_instability": {
        "situation": "Instabilite hemodynamique probable sur la fenetre analysee.",
        "risks": [
            "Hypoperfusion tissulaire peroperatoire",
            "Aggravation hemodynamique rapide si la tendance se poursuit",
        ],
        "recommendations": [
            "Verifier rapidement la mesure et la courbe arterielle",
            "Rechercher une cause immediate: hypovolemie, vasoplegie, profondeur, saignement",
            "Prepararer une action hemodynamique adaptee selon le contexte",
        ],
        "call_mar_reason": "Instabilite hemodynamique critique ou persistante.",
    },
    "respiratory_instability": {
        "situation": "Instabilite respiratoire probable sur la fenetre analysee.",
        "risks": [
            "Hypoxemie peroperatoire",
            "Trouble ventilatoire ou echange gazeux inadequat",
        ],
        "recommendations": [
            "Verifier oxygene, ventilation et qualite des signaux respiratoires",
            "Rechercher rapidement une cause mecanique ou physiologique",
            "Corriger sans delai les parametres ventilatoires ou l'oxygene si necessaire",
        ],
        "call_mar_reason": "Desaturation ou trouble ventilatoire significatif.",
    },
    "airway_mechanics_issue": {
        "situation": "Anomalie mecanique des voies aeriennes possible.",
        "risks": [
            "Pressions de ventilation anormales",
            "Ventilation inefficace si la mecanique se degrade",
        ],
        "recommendations": [
            "Verifier circuit, sonde, ballonnet et position",
            "Rechercher obstacle, bronchospasme ou compliance degradee",
        ],
        "call_mar_reason": "Probleme mecanique respiratoire avec retentissement.",
    },
    "depth_excess": {
        "situation": "Profondeur anesthesique possiblement excessive.",
        "risks": [
            "Depression hemodynamique liee a la profondeur",
            "Surdosage hypnotique possible",
        ],
        "recommendations": [
            "Reevaluer rapidement l'equilibre hypnotique et opioide",
            "Verifier la coherence BIS-contexte clinique",
            "Adapter la profondeur si le contexte le confirme",
        ],
        "call_mar_reason": "Suspicion de surdosage ou depression associee.",
    },
    "light_anesthesia_possible": {
        "situation": "Anesthesie possiblement insuffisante sur la fenetre analysee.",
        "risks": [
            "Stimulation nociceptive non couverte",
            "Allongement hemodynamique lie a une profondeur insuffisante",
        ],
        "recommendations": [
            "Verifier profondeur, analgesie et contexte chirurgical",
            "Confronter BIS, hemodynamique et stimulation en cours",
        ],
        "call_mar_reason": "Suspicion d'anesthesie insuffisante persistante.",
    },
    "hemorrhage_context": {
        "situation": "Contexte compatible avec une complication hemorragique ou transfusionnelle.",
        "risks": [
            "Poursuite d'une instabilite hemodynamique liee au saignement",
            "Besoin transfusionnel ou hemostatique accru",
        ],
        "recommendations": [
            "Verifier le contexte chirurgical et le volume de pertes",
            "Recouper hemodynamique, saignement visible et produits transfuses",
        ],
        "call_mar_reason": "Contexte hemorragique significatif ou transfusionnel.",
    },
    "vasopressor_dependence_context": {
        "situation": "Contexte de soutien vasopresseur peroperatoire notable.",
        "risks": [
            "Instabilite hemodynamique persistante sous support vasoactif",
            "Masquage temporaire d'une cause non corrigee",
        ],
        "recommendations": [
            "Reevaluer la cause de fond de l'instabilite hemodynamique",
            "Verifier la tendance tensionnelle et la reponse au support",
        ],
        "call_mar_reason": "Support vasoactif soutenu ou escalation necessaire.",
    },
    "adverse_outcome_context": {
        "situation": "Contexte perioperatoire associe a un outcome defavorable dans VitalDB.",
        "risks": [
            "Cas globalement a plus haut risque",
            "Besoin d'une vigilance renforcee sur les signes de deterioration",
        ],
        "recommendations": [
            "Interpréter les anomalies avec un seuil de vigilance plus bas",
            "Rapprocher le contexte de la dynamique hemodynamique et respiratoire",
        ],
        "call_mar_reason": "Contexte a risque ou defavorable justifiant une supervision rapprochee.",
    },
    "difficult_airway_context": {
        "situation": "Contexte de voie aerienne potentiellement difficile.",
        "risks": [
            "Gestion des voies aeriennes plus fragile en cas de degradation",
            "Marge de securite respiratoire possiblement reduite",
        ],
        "recommendations": [
            "Garder un niveau d'anticipation eleve sur la ventilation et l'oxygene",
            "Recontextualiser toute anomalie respiratoire avec la difficulte des voies aeriennes",
        ],
        "call_mar_reason": "Voies aeriennes potentiellement difficiles avec retentissement respiratoire.",
    },
    "metabolic_derangement_context": {
        "situation": "Contexte de derangement metabolique ou biologique peroperatoire.",
        "risks": [
            "Aggravation metabolique si la cause n'est pas corrigee",
            "Retentissement hemodynamique ou respiratoire associe",
        ],
        "recommendations": [
            "Recouper l'interpretation waveform avec les anomalies biologiques disponibles",
            "Verifier l'evolution des gaz du sang et des electrolytes si disponible",
        ],
        "call_mar_reason": "Derangement metabolique significatif ou severe.",
    },
    "signal_quality_issue": {
        "situation": "Qualite de signal insuffisante pour une interpretation robuste.",
        "risks": [
            "Surinterpretation d'un artefact",
            "Perte d'information clinique utile",
        ],
        "recommendations": [
            "Verifier capteurs, branchements et qualite de courbe",
            "Interpreter avec prudence tant que le signal n'est pas restaure",
        ],
        "call_mar_reason": None,
    },
    "stable_segment": {
        "situation": "Aucun probleme majeur n'est ressorti sur cette fenetre.",
        "risks": ["Pas de signal fort de deterioration immediate sur cette fenetre"],
        "recommendations": [
            "Poursuivre la surveillance standard",
            "Rester attentif a l'evolution temporelle et au contexte clinique",
        ],
        "call_mar_reason": None,
    },
}


def choose_split(stable_id: str, eval_ratio: float = 0.2) -> str:
    digest = hashlib.md5(stable_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return "eval" if bucket < eval_ratio else "train"


def choose_masked_signals(segment_id: str, signal_names: Iterable[str]) -> list[str]:
    ordered = sorted({name for name in signal_names if name})
    if len(ordered) <= 1:
        return []

    digest = hashlib.md5(f"{segment_id}:partial_wave".encode("utf-8")).digest()
    mask_count = max(1, min(len(ordered) - 1, len(ordered) // 2))
    ranked = sorted(
        ((digest[index % len(digest)], name) for index, name in enumerate(ordered)),
        key=lambda item: (item[0], item[1]),
    )
    return sorted(name for _, name in ranked[:mask_count])


def _fmt(value) -> str:
    return "NA" if value is None else str(value)


def build_prompt_variants(record: ProblemAnalysisRecord) -> list[tuple[str, str, list[str]]]:
    variants: list[tuple[str, str, list[str]]] = [("full_wave", build_user_prompt(record, input_variant="full_wave"), [])]

    variants.append(("no_wave", build_user_prompt(record, input_variant="no_wave"), []))

    masked_signals = choose_masked_signals(record.segment_id, record.signal_features.keys())
    variants.append(
        (
            "partial_wave",
            build_user_prompt(record, input_variant="partial_wave", masked_signals=masked_signals),
            masked_signals,
        )
    )
    return variants


def build_user_prompt(
    record: ProblemAnalysisRecord,
    *,
    input_variant: str = "full_wave",
    masked_signals: list[str] | None = None,
) -> str:
    masked_signals = sorted(masked_signals or [])
    available_signal_names = sorted(record.signal_features)
    lines: list[str] = []
    lines.append("## Segment")
    lines.append(f"- segment_id: {record.segment_id}")
    lines.append(f"- case_id: {record.case_id}")
    lines.append(f"- window_s: {record.start_s} -> {record.end_s}")
    lines.append(f"- input_variant: {input_variant}")

    lines.append("\n## Hypotheses problemes")
    for hypothesis in record.problem_hypotheses[:4]:
        lines.append(
            f"- {hypothesis.problem_id} | severity={hypothesis.severity} | score={hypothesis.score}"
        )

    lines.append("\n## Vitals resumes")
    for key in ["hr", "spo2", "pas", "pad", "pam", "etco2", "fr", "bis"]:
        base = record.vitals_snapshot.get(key)
        low = record.vitals_snapshot.get(f"{key}_min")
        high = record.vitals_snapshot.get(f"{key}_max")
        if base is None and low is None and high is None:
            continue
        lines.append(f"- {key}: current={_fmt(base)} min={_fmt(low)} max={_fmt(high)}")

    lines.append("\n## Features numeriques")
    for key in sorted(record.numeric_features):
        value = record.numeric_features[key]
        if value is not None:
            lines.append(f"- {key}: {value}")

    if input_variant == "no_wave":
        lines.append("\n## Features waveform")
        lines.append("- unavailable: true")
        if available_signal_names:
            lines.append(f"- known_signal_modalities: {', '.join(available_signal_names)}")
        lines.append("- instruction: reason only from vitals, hypotheses and context because waveform features are hidden.")
    else:
        lines.append("\n## Features waveform")
        visible_items = [
            (signal_name, signal)
            for signal_name, signal in sorted(record.signal_features.items())
            if signal_name not in masked_signals
        ]
        for signal_name, signal in visible_items:
            lines.append(
                f"- {signal_name}: coverage={signal.coverage_ratio}, std={_fmt(signal.std)}, amplitude={_fmt(signal.amplitude)}, delta={_fmt(signal.delta)}"
            )
        if input_variant == "partial_wave":
            lines.append("\n## Waveform missingness")
            lines.append(
                f"- masked_signals: {', '.join(masked_signals) if masked_signals else 'none'}"
            )
            lines.append(
                "- instruction: some waveform modalities are intentionally hidden; stay robust to partial monitoring."
            )

    if record.case_complications:
        lines.append("\n## Complications / contexte VitalDB")
        for tag in record.case_complications:
            lines.append(f"- {tag}")

    if record.case_context:
        lines.append("\n## Contexte cas")
        for key, value in sorted(record.case_context.items()):
            if value is not None:
                lines.append(f"- {key}: {value}")

    lines.append("\n## Consigne")
    lines.append("Produis un JSON avec situation, risks, recommendations, call_mar, call_mar_reason et confidence.")
    return "\n".join(lines)


def build_reference_target(record: ProblemAnalysisRecord) -> ExplanationTarget:
    primary = record.primary_problem_id or "stable_segment"
    template = PROBLEM_TEMPLATES.get(primary, PROBLEM_TEMPLATES["stable_segment"])
    top_hypothesis = record.problem_hypotheses[0] if record.problem_hypotheses else None
    score = top_hypothesis.score if top_hypothesis else 0.5
    severity = top_hypothesis.severity if top_hypothesis else "info"

    situation_parts = [template["situation"]]
    if severity == "critical":
        situation_parts.append("Le niveau de priorite est critique.")
    elif severity == "warning":
        situation_parts.append("Une reevaluation rapprochee est necessaire.")

    if record.weak_labels:
        weak = ", ".join(record.weak_labels[:3])
        situation_parts.append(f"Signaux heuristiques associes: {weak}.")
    if record.case_complications:
        context_tags = ", ".join(record.case_complications[:3])
        situation_parts.append(f"Contexte VitalDB associe: {context_tags}.")

    risks = list(template["risks"])
    for hypothesis in record.problem_hypotheses[1:3]:
        risk_text = hypothesis.problem_id.replace("_", " ")
        risks.append(f"Surveiller aussi le risque associe a {risk_text}.")
    risks = risks[:6]

    recommendations = list(template["recommendations"])
    if primary == "hemodynamic_instability":
        if record.vitals_snapshot.get("pam_min") is not None and record.vitals_snapshot["pam_min"] < 55:
            recommendations.append("Alerter sans delai si l'hypotension reste profonde ou s'aggrave.")
    if primary == "respiratory_instability":
        if record.vitals_snapshot.get("spo2_min") is not None and record.vitals_snapshot["spo2_min"] < 88:
            recommendations.append("Reevaluer immediatement l'oxygene et la ventilation si la desaturation persiste.")
    if primary == "signal_quality_issue":
        recommendations = recommendations[:2]
    recommendations = recommendations[:6]

    call_mar = severity == "critical"
    if primary in {"hemodynamic_instability", "respiratory_instability"} and score >= 0.75:
        call_mar = True
    call_mar_reason = template["call_mar_reason"] if call_mar else None

    confidence = min(max(round(0.35 + 0.6 * score, 3), 0.0), 0.95)

    return ExplanationTarget(
        situation=" ".join(situation_parts)[:400],
        risks=risks,
        recommendations=recommendations,
        call_mar=call_mar,
        call_mar_reason=call_mar_reason,
        confidence=confidence,
    )
