"""
CHARLES — KB Loader.

Charge tous les fichiers YAML de la Knowledge Base au démarrage
et fournit un accès structuré pour l'alert engine et le LLM.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("charles.kb")


class KnowledgeBase:
    """Knowledge Base clinique chargée depuis les YAML."""

    def __init__(self, kb_path: str | Path = "kb"):
        self.path = Path(kb_path)
        self.data: dict[str, Any] = {}
        self._loaded = False

    def load(self):
        """Charge tous les fichiers YAML du dossier KB."""
        if not self.path.exists():
            logger.warning("KB path %s does not exist", self.path)
            return

        for yaml_file in sorted(self.path.glob("*.yaml")):
            key = yaml_file.stem  # e.g. "monitoring_params"
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    self.data[key] = yaml.safe_load(f)
                logger.info("KB loaded: %s", yaml_file.name)
            except Exception as e:
                logger.error("KB failed to load %s: %s", yaml_file.name, e)

        self._loaded = True
        logger.info("KB ready — %d files loaded", len(self.data))

    @property
    def loaded(self) -> bool:
        return self._loaded

    # ── Accès structuré ────────────────────────────────────────

    @property
    def monitoring_params(self) -> dict:
        return self.data.get("monitoring_params", {})

    @property
    def populations(self) -> dict:
        return self.data.get("populations", {})

    @property
    def drugs(self) -> dict:
        return self.data.get("drugs_anesthesia", {})

    @property
    def surgeries(self) -> dict:
        return self.data.get("surgeries", {})

    @property
    def complications(self) -> dict:
        return self.data.get("complications_perop", {})

    @property
    def algorithms(self) -> dict:
        return self.data.get("algorithms", {})

    @property
    def scores(self) -> dict:
        return self.data.get("scores_cliniques", {})

    @property
    def terrains(self) -> dict:
        return self.data.get("terrains", {})

    @property
    def reference_trends(self) -> dict:
        return self.data.get("reference_trends", {})

    # ── Requêtes utiles ────────────────────────────────────────

    def get_thresholds_for_population(self, population: str = "adulte_standard") -> dict:
        """Retourne les seuils adaptés à une population donnée.
        
        Fusionne les seuils de monitoring_params avec les adaptations
        de la population (gériatrique, obèse, etc.).
        """
        # Seuils de base depuis monitoring_params
        base_thresholds = self._extract_base_thresholds()

        # Adaptations population
        pops = self.populations.get("populations", {})
        pop = pops.get(population, {})
        adaptations = pop.get("alertes_adaptees", {})

        # Appliquer les adaptations
        if "pam_seuil_bas" in adaptations:
            base_thresholds.setdefault("pam", {})["warning_low"] = adaptations["pam_seuil_bas"]
        if "temperature_seuil_bas" in adaptations:
            base_thresholds.setdefault("temp", {})["warning_low"] = adaptations["temperature_seuil_bas"]
        if "spo2_seuil_bas" in adaptations:
            base_thresholds.setdefault("spo2", {})["warning_low"] = adaptations["spo2_seuil_bas"]
        if "bis_seuil_bas" in adaptations:
            base_thresholds.setdefault("bis", {})["warning_low"] = adaptations["bis_seuil_bas"]
        if "etco2_seuil_haut" in adaptations:
            base_thresholds.setdefault("etco2", {})["warning_high"] = adaptations["etco2_seuil_haut"]
        if "pip_seuil_haut" in adaptations:
            base_thresholds.setdefault("ppeak", {})["warning_high"] = adaptations["pip_seuil_haut"]

        return base_thresholds

    def _extract_base_thresholds(self) -> dict:
        """Extrait les seuils depuis monitoring_params.yaml → format alert engine."""
        thresholds = {}
        categories = self.monitoring_params.get("categories", {})

        # Mapping abréviation KB → nom param alert engine
        abbrev_map = {
            "HR": "hr", "PAS": "pas", "PAD": "pad", "PAM": "pam",
            "SpO2": "spo2", "EtCO2": "etco2", "FR": "fr",
            "BIS": "bis", "SR": "sr",
        }

        for cat_data in categories.values():
            params = cat_data.get("parametres", {})
            for param_data in params.values():
                abbrev = param_data.get("abbreviation", "")
                # Handle "CO / DC" style abbreviations
                abbr_key = abbrev.split("/")[0].strip() if "/" in abbrev else abbrev
                engine_key = abbrev_map.get(abbr_key)
                if not engine_key:
                    continue

                seuils = param_data.get("seuils_charles", {})
                if not seuils:
                    continue

                entry = {}
                if "critique_bas" in seuils:
                    entry["critical_low"] = seuils["critique_bas"]
                if "alerte_basse" in seuils:
                    entry["warning_low"] = seuils["alerte_basse"]
                if "critique_haut" in seuils:
                    entry["critical_high"] = seuils["critique_haut"]
                if "alerte_haute" in seuils:
                    entry["warning_high"] = seuils["alerte_haute"]

                entry["label"] = param_data.get("label_fr", abbrev)
                entry["unit"] = param_data.get("unite", "")

                thresholds[engine_key] = entry

        return thresholds

    def get_context_for_llm(
        self,
        surgery_type: str | None = None,
        population: str | None = None,
        terrain: list[str] | None = None,
        active_drugs: list[str] | None = None,
    ) -> str:
        """Construit un contexte textuel KB pour enrichir un prompt LLM."""
        sections = []

        # Population
        if population:
            pops = self.populations.get("populations", {})
            pop_data = pops.get(population, {})
            if pop_data:
                sections.append(f"## Population: {pop_data.get('label_fr', population)}")
                for p in pop_data.get("particularites_anesthesiques", []):
                    sections.append(f"- {p}")

        # Chirurgie
        if surgery_type:
            all_surgeries = self.surgeries
            for dept_data in all_surgeries.get("departements", {}).values():
                for proc in dept_data.get("procedures", []):
                    if proc.get("id") == surgery_type or surgery_type.lower() in proc.get("nom_fr", "").lower():
                        sections.append(f"## Chirurgie: {proc.get('nom_fr', surgery_type)}")
                        sections.append(f"- Durée: {proc.get('duree_moyenne_min', '?')} min")
                        sections.append(f"- Risque hémorragique: {proc.get('risque_hemorragique', '?')}")
                        for r in proc.get("risques_specifiques", []):
                            sections.append(f"- Risque: {r}")
                        break

        # Terrains / comorbidités
        if terrain:
            terrains_data = self.terrains.get("terrains", {})
            for t in terrain:
                for sys_data in terrains_data.values():
                    for pathology in sys_data.get("pathologies", []):
                        if t.lower() in pathology.get("id", "").lower() or t.lower() in pathology.get("nom_fr", "").lower():
                            sections.append(f"## Terrain: {pathology.get('nom_fr', t)}")
                            for imp in pathology.get("impact_anesthesique", []):
                                sections.append(f"- {imp}")
                            break

        # Médicaments administrés
        if active_drugs:
            drugs_data = self.drugs
            for drug_name in active_drugs:
                for cat_data in drugs_data.get("categories", {}).values():
                    for mol in cat_data.get("molecules", []):
                        if drug_name.lower() in mol.get("dci", "").lower():
                            sections.append(f"## Médicament: {mol.get('dci', drug_name)}")
                            for ei in mol.get("effets_indesirables", []):
                                sections.append(f"- EI: {ei}")
                            break

        return "\n".join(sections) if sections else "Pas de contexte KB spécifique disponible."

