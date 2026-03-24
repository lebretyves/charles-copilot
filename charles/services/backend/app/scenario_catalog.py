"""
CHARLES — Catalogue COMPLET de scénarios VitalDB.

Expose les 74 colonnes de clinical_metadata.csv comme critères
filtrables afin qu'aucun cas ne soit non-répertorié ou invisible.
Types de filtres : single, toggle, range, search.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np

logger = logging.getLogger("charles.catalog")

# ── Constantes ─────────────────────────────────────────────────
AGE_BINS = [0, 18, 40, 60, 75, 120]
AGE_LABELS = [
    "Pédiatrique (<18)", "Adulte jeune (18-40)",
    "Adulte (40-60)", "Senior (60-75)", "Gériatrique (>75)",
]
ASA_LABELS = {
    1: "ASA 1 — Patient sain",
    2: "ASA 2 — Affection systémique légère",
    3: "ASA 3 — Affection systémique sévère",
    4: "ASA 4 — Menace vitale permanente",
    5: "ASA 5 — Moribond",
    6: "ASA 6 — Mort cérébrale / don d'organes",
}
DURATION_BINS = [0, 60, 120, 180, 300, 480, 99999]
DURATION_LABELS = ["< 1h", "1–2h", "2–3h", "3–5h", "5–8h", "> 8h"]


class ScenarioCatalog:
    """Catalogue exhaustif de cas VitalDB pour la sélection de scénarios."""

    def __init__(self, metadata_path: str | Path | None = None,
                 cases_dir: str | Path | None = None):
        self.metadata_path = metadata_path
        self.cases_dir = cases_dir
        self.df: pd.DataFrame | None = None
        self.loaded = False

    # ════════════════════════════════════════════════════════════
    #  CHARGEMENT
    # ════════════════════════════════════════════════════════════
    def load(self):
        if not self.metadata_path or not Path(self.metadata_path).exists():
            logger.warning("clinical_metadata.csv non trouvé: %s", self.metadata_path)
            return

        self.df = pd.read_csv(self.metadata_path)

        # — Colonnes dérivées ————————————————————————————————————
        # Tranche d'âge
        self.df["age_group"] = pd.cut(
            self.df["age"], bins=AGE_BINS, labels=AGE_LABELS, right=False,
        )
        # ASA int
        self.df["asa_int"] = self.df["asa"].fillna(0).astype(int)
        # Flags comorbidités
        self.df["preop_htn"] = self.df["preop_htn"].fillna(0).astype(int)
        self.df["preop_dm"] = self.df["preop_dm"].fillna(0).astype(int)
        self.df["emop"] = self.df["emop"].fillna(0).astype(int)
        # ECG anormal
        self.df["ecg_anormal"] = (
            self.df["preop_ecg"].notna()
            & (self.df["preop_ecg"] != "Normal Sinus Rhythm")
        ).astype(int)
        # EFR
        pft = self.df["preop_pft"].fillna("")
        self.df["pft_obstructive"] = pft.str.contains("obstructive", case=False).astype(int)
        self.df["pft_restrictive"] = pft.str.contains("restrictive", case=False).astype(int)
        self.df["pft_anormal"] = (self.df["pft_obstructive"] | self.df["pft_restrictive"]).astype(int)
        # Anomalies biologiques préop
        self.df["bio_anemie"] = (self.df["preop_hb"] < 10).fillna(False).astype(int)
        self.df["bio_thrombopenie"] = (self.df["preop_plt"] < 100).fillna(False).astype(int)
        self.df["bio_coagulopathie"] = (self.df["preop_pt"] < 60).fillna(False).astype(int)
        self.df["bio_hyponatremie"] = (self.df["preop_na"] < 135).fillna(False).astype(int)
        self.df["bio_hyperkaliemie"] = (self.df["preop_k"] > 5.5).fillna(False).astype(int)
        self.df["bio_hyperglycemie"] = (self.df["preop_gluc"] > 200).fillna(False).astype(int)
        self.df["bio_hypoalb"] = (self.df["preop_alb"] < 3).fillna(False).astype(int)
        self.df["bio_irc"] = (self.df["preop_cr"] > 1.5).fillna(False).astype(int)
        self.df["bio_cytolyse"] = (self.df["preop_ast"] > 40).fillna(False).astype(int)
        # Durée totale (minutes)
        self.df["duration_min"] = (self.df["caseend"].fillna(0) / 60).round(1)
        self.df["duration_group"] = pd.cut(
            self.df["duration_min"], bins=DURATION_BINS, labels=DURATION_LABELS, right=False,
        )
        # Accès vasculaires — flags booléens
        self.df["has_aline"] = self.df["aline1"].notna().astype(int)
        self.df["has_cline"] = self.df["cline1"].notna().astype(int)
        self.df["has_iv2"] = self.df["iv2"].notna().astype(int)
        # Drogues perop — flags utilisation
        self.df["has_propofol"] = (self.df["intraop_ppf"].fillna(0) > 0).astype(int)
        self.df["has_midazolam"] = (self.df["intraop_mdz"].fillna(0) > 0).astype(int)
        self.df["has_fentanyl"] = (self.df["intraop_ftn"].fillna(0) > 0).astype(int)
        self.df["has_rocuronium"] = (self.df["intraop_rocu"].fillna(0) > 0).astype(int)
        self.df["has_vecuronium"] = (self.df["intraop_vecu"].fillna(0) > 0).astype(int)
        self.df["has_ephedrine"] = (self.df["intraop_eph"].fillna(0) > 0).astype(int)
        self.df["has_phenylephrine"] = (self.df["intraop_phe"].fillna(0) > 0).astype(int)
        self.df["has_epinephrine"] = (self.df["intraop_epi"].fillna(0) > 0).astype(int)
        self.df["has_calcium"] = (self.df["intraop_ca"].fillna(0) > 0).astype(int)
        self.df["has_transfusion"] = (self.df["intraop_rbc"].fillna(0) > 0).astype(int)
        self.df["has_ffp"] = (self.df["intraop_ffp"].fillna(0) > 0).astype(int)
        self.df["has_colloid"] = (self.df["intraop_colloid"].fillna(0) > 0).astype(int)
        # Gaz du sang préop — disponibilité
        self.df["has_blood_gas"] = self.df["preop_ph"].notna().astype(int)

        # — Fichiers parquet disponibles ————————————————————————
        if self.cases_dir:
            available = set()
            cases_path = Path(self.cases_dir)
            if cases_path.exists():
                for f in cases_path.glob("case_*.parquet"):
                    try:
                        available.add(int(f.stem.replace("case_", "")))
                    except ValueError:
                        pass
            self.df["has_parquet"] = self.df["caseid"].isin(available)
            logger.info("Catalogue chargé: %d cas, %d avec parquet",
                        len(self.df), self.df["has_parquet"].sum())
        else:
            self.df["has_parquet"] = True
            logger.info("Catalogue chargé: %d cas (parquet non vérifié)", len(self.df))

        self.loaded = True

    # ════════════════════════════════════════════════════════════
    #  CATALOGUE STRUCTURÉ  — expose les 74 colonnes
    # ════════════════════════════════════════════════════════════
    def get_catalog(self) -> dict[str, Any]:
        if not self.loaded or self.df is None:
            return {"loaded": False, "categories": {}}

        df = self.df[self.df["has_parquet"]].copy()

        return {
            "loaded": True,
            "total_cases": len(df),
            "categories": {
                # ── 1. Profil Patient ──────────────────────────
                "profil_patient": {
                    "label": "Profil Patient",
                    "icon": "👤",
                    "subcategories": {
                        "age_group": {
                            "label": "Tranche d'âge",
                            "type": "single",
                            "options": self._value_counts(df, "age_group", AGE_LABELS),
                        },
                        "age": self._range_desc(df, "age", "Âge exact", "ans"),
                        "sex": {
                            "label": "Sexe",
                            "type": "single",
                            "options": self._value_counts(df, "sex", {"M": "Homme", "F": "Femme"}),
                        },
                        "asa": {
                            "label": "Score ASA",
                            "type": "single",
                            "options": self._asa_counts(df),
                        },
                        "bmi_range": {
                            "label": "Corpulence (IMC)",
                            "type": "single",
                            "options": self._bmi_counts(df),
                        },
                        "height": self._range_desc(df, "height", "Taille", "cm"),
                        "weight": self._range_desc(df, "weight", "Poids", "kg"),
                    },
                },
                # ── 2. Chirurgie ───────────────────────────────
                "chirurgie": {
                    "label": "Chirurgie",
                    "icon": "🔪",
                    "subcategories": {
                        "department": {
                            "label": "Spécialité",
                            "type": "single",
                            "options": self._value_counts(df, "department"),
                        },
                        "optype": {
                            "label": "Type d'intervention",
                            "type": "single",
                            "options": self._value_counts(df, "optype"),
                        },
                        "approach": {
                            "label": "Voie d'abord",
                            "type": "single",
                            "options": self._value_counts(df, "approach"),
                        },
                        "position": {
                            "label": "Position opératoire",
                            "type": "single",
                            "options": self._value_counts(df, "position"),
                        },
                        "dx": {
                            "label": "Diagnostic (recherche texte)",
                            "type": "search",
                            "top_values": self._value_counts_top(df, "dx", 20),
                            "total_unique": int(df["dx"].nunique()),
                        },
                        "opname": {
                            "label": "Nom de l'intervention (recherche texte)",
                            "type": "search",
                            "top_values": self._value_counts_top(df, "opname", 20),
                            "total_unique": int(df["opname"].nunique()),
                        },
                        "emop": {
                            "label": "Urgence",
                            "type": "toggle",
                            "count": int(df["emop"].sum()),
                        },
                        "duration_group": {
                            "label": "Durée totale",
                            "type": "single",
                            "options": self._value_counts(df, "duration_group", DURATION_LABELS),
                        },
                        "duration_min": self._range_desc(df, "duration_min", "Durée exacte", "min"),
                    },
                },
                # ── 3. Anesthésie ──────────────────────────────
                "anesthesie": {
                    "label": "Anesthésie",
                    "icon": "💉",
                    "subcategories": {
                        "ane_type": {
                            "label": "Technique anesthésique",
                            "type": "single",
                            "options": self._value_counts(df, "ane_type"),
                        },
                        "airway": {
                            "label": "Voie aérienne",
                            "type": "single",
                            "options": self._value_counts(df, "airway"),
                        },
                        "cormack": {
                            "label": "Cormack-Lehane",
                            "type": "single",
                            "options": self._value_counts(df, "cormack"),
                        },
                        "tubesize": {
                            "label": "Taille de sonde IOT",
                            "type": "single",
                            "options": self._value_counts(df, "tubesize"),
                        },
                        "dltubesize": {
                            "label": "Sonde double lumière",
                            "type": "single",
                            "options": self._value_counts(df, "dltubesize"),
                        },
                        "lmasize": {
                            "label": "Masque laryngé (LMA)",
                            "type": "single",
                            "options": self._value_counts(df, "lmasize"),
                        },
                    },
                },
                # ── 4. Antécédents / Comorbidités ──────────────
                "antecedents": {
                    "label": "Antécédents / Comorbidités",
                    "icon": "🩺",
                    "subcategories": {
                        "preop_htn": {
                            "label": "HTA",
                            "type": "toggle",
                            "count": int(df["preop_htn"].sum()),
                        },
                        "preop_dm": {
                            "label": "Diabète",
                            "type": "toggle",
                            "count": int(df["preop_dm"].sum()),
                        },
                        "ecg_anormal": {
                            "label": "ECG anormal (ACFA, BAV, BBD…)",
                            "type": "toggle",
                            "count": int(df["ecg_anormal"].sum()),
                        },
                        "preop_ecg": {
                            "label": "Type d'anomalie ECG",
                            "type": "single",
                            "options": self._value_counts(df, "preop_ecg"),
                        },
                        "pft_anormal": {
                            "label": "EFR anormale",
                            "type": "toggle",
                            "count": int(df["pft_anormal"].sum()),
                        },
                        "preop_pft": {
                            "label": "Type EFR",
                            "type": "single",
                            "options": self._value_counts(df, "preop_pft"),
                        },
                    },
                },
                # ── 5. Biologie préopératoire ──────────────────
                "biologie_preop": {
                    "label": "Biologie préopératoire",
                    "icon": "🧪",
                    "subcategories": {
                        "bio_anemie": {
                            "label": "Anémie (Hb < 10 g/dL)",
                            "type": "toggle",
                            "count": int(df["bio_anemie"].sum()),
                        },
                        "preop_hb": self._range_desc(df, "preop_hb", "Hémoglobine", "g/dL"),
                        "bio_thrombopenie": {
                            "label": "Thrombopénie (PLT < 100k)",
                            "type": "toggle",
                            "count": int(df["bio_thrombopenie"].sum()),
                        },
                        "preop_plt": self._range_desc(df, "preop_plt", "Plaquettes", "×10³/µL"),
                        "bio_coagulopathie": {
                            "label": "Coagulopathie (PT < 60%)",
                            "type": "toggle",
                            "count": int(df["bio_coagulopathie"].sum()),
                        },
                        "preop_pt": self._range_desc(df, "preop_pt", "TP (%)", "%"),
                        "preop_aptt": self._range_desc(df, "preop_aptt", "TCA (aPTT)", "s"),
                        "bio_hyponatremie": {
                            "label": "Hyponatrémie (Na < 135)",
                            "type": "toggle",
                            "count": int(df["bio_hyponatremie"].sum()),
                        },
                        "preop_na": self._range_desc(df, "preop_na", "Natrémie", "mmol/L"),
                        "bio_hyperkaliemie": {
                            "label": "Hyperkaliémie (K > 5.5)",
                            "type": "toggle",
                            "count": int(df["bio_hyperkaliemie"].sum()),
                        },
                        "preop_k": self._range_desc(df, "preop_k", "Kaliémie", "mmol/L"),
                        "bio_hyperglycemie": {
                            "label": "Hyperglycémie (Gluc > 200)",
                            "type": "toggle",
                            "count": int(df["bio_hyperglycemie"].sum()),
                        },
                        "preop_gluc": self._range_desc(df, "preop_gluc", "Glycémie", "mg/dL"),
                        "bio_hypoalb": {
                            "label": "Hypoalbuminémie (Alb < 3)",
                            "type": "toggle",
                            "count": int(df["bio_hypoalb"].sum()),
                        },
                        "preop_alb": self._range_desc(df, "preop_alb", "Albumine", "g/dL"),
                        "bio_cytolyse": {
                            "label": "Cytolyse hépatique (AST > 40)",
                            "type": "toggle",
                            "count": int(df["bio_cytolyse"].sum()),
                        },
                        "preop_ast": self._range_desc(df, "preop_ast", "AST", "UI/L"),
                        "preop_alt": self._range_desc(df, "preop_alt", "ALT", "UI/L"),
                        "bio_irc": {
                            "label": "IRC (Créat > 1.5)",
                            "type": "toggle",
                            "count": int(df["bio_irc"].sum()),
                        },
                        "preop_bun": self._range_desc(df, "preop_bun", "Urée (BUN)", "mg/dL"),
                        "preop_cr": self._range_desc(df, "preop_cr", "Créatinine", "mg/dL"),
                    },
                },
                # ── 6. Gaz du sang préopératoires ──────────────
                "gaz_du_sang": {
                    "label": "Gaz du sang préopératoires",
                    "icon": "🫁",
                    "subcategories": {
                        "has_blood_gas": {
                            "label": "GDS disponible",
                            "type": "toggle",
                            "count": int(df["has_blood_gas"].sum()),
                        },
                        "preop_ph": self._range_desc(df, "preop_ph", "pH artériel", ""),
                        "preop_pao2": self._range_desc(df, "preop_pao2", "PaO₂", "mmHg"),
                        "preop_paco2": self._range_desc(df, "preop_paco2", "PaCO₂", "mmHg"),
                        "preop_sao2": self._range_desc(df, "preop_sao2", "SaO₂", "%"),
                        "preop_hco3": self._range_desc(df, "preop_hco3", "HCO₃⁻", "mmol/L"),
                        "preop_be": self._range_desc(df, "preop_be", "Base Excess", "mmol/L"),
                    },
                },
                # ── 7. Accès vasculaires ───────────────────────
                "acces_vasculaires": {
                    "label": "Accès vasculaires",
                    "icon": "🔌",
                    "subcategories": {
                        "iv1": {
                            "label": "VVP 1 (site)",
                            "type": "single",
                            "options": self._value_counts(df, "iv1"),
                        },
                        "has_iv2": {
                            "label": "2ᵉ VVP",
                            "type": "toggle",
                            "count": int(df["has_iv2"].sum()),
                        },
                        "iv2": {
                            "label": "VVP 2 (site)",
                            "type": "single",
                            "options": self._value_counts(df, "iv2"),
                        },
                        "has_aline": {
                            "label": "Cathéter artériel",
                            "type": "toggle",
                            "count": int(df["has_aline"].sum()),
                        },
                        "aline1": {
                            "label": "Artère 1 (site)",
                            "type": "single",
                            "options": self._value_counts(df, "aline1"),
                        },
                        "aline2": {
                            "label": "Artère 2 (site)",
                            "type": "single",
                            "options": self._value_counts(df, "aline2"),
                        },
                        "has_cline": {
                            "label": "Voie veineuse centrale",
                            "type": "toggle",
                            "count": int(df["has_cline"].sum()),
                        },
                        "cline1": {
                            "label": "VVC 1 (site)",
                            "type": "single",
                            "options": self._value_counts(df, "cline1"),
                        },
                        "cline2": {
                            "label": "VVC 2 (site)",
                            "type": "single",
                            "options": self._value_counts(df, "cline2"),
                        },
                    },
                },
                # ── 8. Données peropératoires ──────────────────
                "peroperatoire": {
                    "label": "Données peropératoires",
                    "icon": "📈",
                    "subcategories": {
                        "intraop_ebl": self._range_desc(df, "intraop_ebl", "Pertes sanguines (EBL)", "mL"),
                        "intraop_uo": self._range_desc(df, "intraop_uo", "Diurèse", "mL"),
                        "intraop_crystalloid": self._range_desc(df, "intraop_crystalloid", "Cristalloïdes", "mL"),
                        "has_colloid": {
                            "label": "Colloïdes administrés",
                            "type": "toggle",
                            "count": int(df["has_colloid"].sum()),
                        },
                        "intraop_colloid": self._range_desc(df, "intraop_colloid", "Colloïdes", "mL"),
                        "has_transfusion": {
                            "label": "Transfusion CGR",
                            "type": "toggle",
                            "count": int(df["has_transfusion"].sum()),
                        },
                        "intraop_rbc": self._range_desc(df, "intraop_rbc", "CGR (unités)", "U"),
                        "has_ffp": {
                            "label": "PFC administré",
                            "type": "toggle",
                            "count": int(df["has_ffp"].sum()),
                        },
                        "intraop_ffp": self._range_desc(df, "intraop_ffp", "PFC (unités)", "U"),
                    },
                },
                # ── 9. Drogues peropératoires ──────────────────
                "drogues_perop": {
                    "label": "Drogues peropératoires",
                    "icon": "💊",
                    "subcategories": {
                        "has_propofol": {
                            "label": "Propofol utilisé",
                            "type": "toggle",
                            "count": int(df["has_propofol"].sum()),
                        },
                        "intraop_ppf": self._range_desc(df, "intraop_ppf", "Propofol dose", "mg"),
                        "has_midazolam": {
                            "label": "Midazolam utilisé",
                            "type": "toggle",
                            "count": int(df["has_midazolam"].sum()),
                        },
                        "intraop_mdz": self._range_desc(df, "intraop_mdz", "Midazolam dose", "mg"),
                        "has_fentanyl": {
                            "label": "Fentanyl utilisé",
                            "type": "toggle",
                            "count": int(df["has_fentanyl"].sum()),
                        },
                        "intraop_ftn": self._range_desc(df, "intraop_ftn", "Fentanyl dose", "µg"),
                        "has_rocuronium": {
                            "label": "Rocuronium utilisé",
                            "type": "toggle",
                            "count": int(df["has_rocuronium"].sum()),
                        },
                        "intraop_rocu": self._range_desc(df, "intraop_rocu", "Rocuronium dose", "mg"),
                        "has_vecuronium": {
                            "label": "Vécuronium utilisé",
                            "type": "toggle",
                            "count": int(df["has_vecuronium"].sum()),
                        },
                        "has_ephedrine": {
                            "label": "Éphédrine administrée",
                            "type": "toggle",
                            "count": int(df["has_ephedrine"].sum()),
                        },
                        "intraop_eph": self._range_desc(df, "intraop_eph", "Éphédrine dose", "mg"),
                        "has_phenylephrine": {
                            "label": "Phényléphrine administrée",
                            "type": "toggle",
                            "count": int(df["has_phenylephrine"].sum()),
                        },
                        "intraop_phe": self._range_desc(df, "intraop_phe", "Phényléphrine dose", "µg"),
                        "has_epinephrine": {
                            "label": "Adrénaline administrée",
                            "type": "toggle",
                            "count": int(df["has_epinephrine"].sum()),
                        },
                        "intraop_epi": self._range_desc(df, "intraop_epi", "Adrénaline dose", "µg"),
                        "has_calcium": {
                            "label": "Calcium administré",
                            "type": "toggle",
                            "count": int(df["has_calcium"].sum()),
                        },
                        "intraop_ca": self._range_desc(df, "intraop_ca", "Calcium dose", "mg"),
                    },
                },
                # ── 10. Devenir ────────────────────────────────
                "devenir": {
                    "label": "Devenir du patient",
                    "icon": "📊",
                    "subcategories": {
                        "death_inhosp": {
                            "label": "Décès hospitalier",
                            "type": "toggle",
                            "count": int(df["death_inhosp"].fillna(0).sum()),
                        },
                        "icu": {
                            "label": "Passage en réanimation",
                            "type": "toggle",
                            "count": int((df["icu_days"].fillna(0) > 0).sum()),
                        },
                        "icu_days": self._range_desc(df, "icu_days", "Jours en réa", "j"),
                    },
                },
                # ── 11. Scénarios synthétiques ─────────────────
                "scenarios_synthetiques": {
                    "label": "Scénarios Synthétiques (prédéfinis)",
                    "icon": "🎭",
                    "subcategories": {
                        "scenario": {
                            "label": "Scénario",
                            "type": "single",
                            "options": [
                                {"value": "normal", "label": "Normal — Cholécystectomie ASA 1", "count": None},
                                {"value": "hypotension", "label": "Hypotension progressive post-induction", "count": None},
                                {"value": "desaturation", "label": "Intubation difficile — désaturation", "count": None},
                                {"value": "anaphylaxie", "label": "Anaphylaxie peropératoire", "count": None},
                                {"value": "hemorragie", "label": "Hémorragie peropératoire", "count": None},
                            ],
                        },
                    },
                },
            },
        }

    # ════════════════════════════════════════════════════════════
    #  RECHERCHE / FILTRAGE
    # ════════════════════════════════════════════════════════════
    def search_cases(self, filters: dict[str, Any]) -> dict[str, Any]:
        if not self.loaded or self.df is None:
            return {"total_matches": 0, "cases": []}

        df = self.df[self.df["has_parquet"]].copy()

        # ── Filtres catégoriels (single = exact match) ─────────
        _SINGLE_COLS = {
            "sex": "sex", "department": "department", "optype": "optype",
            "approach": "approach", "position": "position",
            "ane_type": "ane_type", "airway": "airway", "cormack": "cormack",
            "preop_ecg": "preop_ecg", "preop_pft": "preop_pft",
            "iv1": "iv1", "iv2": "iv2",
            "aline1": "aline1", "aline2": "aline2",
            "cline1": "cline1", "cline2": "cline2",
            "tubesize": "tubesize", "dltubesize": "dltubesize",
            "lmasize": "lmasize", "duration_group": "duration_group",
        }
        for fkey, col in _SINGLE_COLS.items():
            val = filters.get(fkey)
            if val:
                df = df[df[col].astype(str) == str(val)]

        # Tranche d'âge
        val = filters.get("age_group")
        if val:
            df = df[df["age_group"] == val]

        # ASA
        val = filters.get("asa")
        if val:
            df = df[df["asa_int"] == int(val)]

        # BMI range (bins pré-définis)
        val = filters.get("bmi_range")
        if val:
            bmi = df["bmi"]
            if val == "underweight":
                df = df[bmi < 18.5]
            elif val == "normal":
                df = df[(bmi >= 18.5) & (bmi < 25)]
            elif val == "overweight":
                df = df[(bmi >= 25) & (bmi < 30)]
            elif val == "obese":
                df = df[bmi >= 30]

        # ── Filtres toggle (bool → ==1 / >0) ──────────────────
        _TOGGLE_DIRECT = [
            "preop_htn", "preop_dm", "ecg_anormal", "pft_anormal",
            "bio_anemie", "bio_thrombopenie", "bio_coagulopathie",
            "bio_hyponatremie", "bio_hyperkaliemie", "bio_hyperglycemie",
            "bio_hypoalb", "bio_irc", "bio_cytolyse",
            "has_aline", "has_cline", "has_iv2", "has_blood_gas",
            "has_colloid", "has_transfusion", "has_ffp",
            "has_propofol", "has_midazolam", "has_fentanyl",
            "has_rocuronium", "has_vecuronium",
            "has_ephedrine", "has_phenylephrine", "has_epinephrine",
            "has_calcium", "emop",
        ]
        for key in _TOGGLE_DIRECT:
            if filters.get(key):
                df = df[df[key] == 1]

        if filters.get("death_inhosp"):
            df = df[df["death_inhosp"].fillna(0) == 1]

        if filters.get("icu"):
            df = df[df["icu_days"].fillna(0) > 0]

        # ── Filtres range (min / max) ──────────────────────────
        _RANGE_COLS = [
            "age", "height", "weight", "duration_min",
            "preop_hb", "preop_plt", "preop_pt", "preop_aptt",
            "preop_na", "preop_k", "preop_gluc", "preop_alb",
            "preop_ast", "preop_alt", "preop_bun", "preop_cr",
            "preop_ph", "preop_pao2", "preop_paco2", "preop_sao2",
            "preop_hco3", "preop_be",
            "intraop_ebl", "intraop_uo", "intraop_crystalloid",
            "intraop_colloid", "intraop_rbc", "intraop_ffp",
            "intraop_ppf", "intraop_mdz", "intraop_ftn",
            "intraop_rocu", "intraop_eph", "intraop_phe",
            "intraop_epi", "intraop_ca", "icu_days",
        ]
        for col in _RANGE_COLS:
            lo = filters.get(f"{col}_min")
            hi = filters.get(f"{col}_max")
            if lo is not None:
                df = df[df[col].fillna(float("-inf")) >= float(lo)]
            if hi is not None:
                df = df[df[col].fillna(float("inf")) <= float(hi)]

        # ── Filtres texte (search = contient) ──────────────────
        for col in ("dx", "opname"):
            val = filters.get(col)
            if val:
                df = df[df[col].fillna("").str.contains(str(val), case=False, na=False)]

        # ── Résultats ──────────────────────────────────────────
        total = len(df)
        results = []
        for _, row in df.head(50).iterrows():
            asa_val = int(row["asa"]) if pd.notna(row["asa"]) else None
            dur = round(float(row["duration_min"])) if pd.notna(row["duration_min"]) else None
            results.append({
                "caseid": int(row["caseid"]),
                "age": int(row["age"]) if pd.notna(row["age"]) else None,
                "sex": row["sex"] if pd.notna(row["sex"]) else None,
                "asa": asa_val,
                "asa_label": ASA_LABELS.get(asa_val, ""),
                "bmi": round(float(row["bmi"]), 1) if pd.notna(row["bmi"]) else None,
                "height": round(float(row["height"]), 1) if pd.notna(row["height"]) else None,
                "weight": round(float(row["weight"]), 1) if pd.notna(row["weight"]) else None,
                "department": row["department"] if pd.notna(row["department"]) else None,
                "optype": row["optype"] if pd.notna(row["optype"]) else None,
                "opname": row["opname"] if pd.notna(row["opname"]) else None,
                "dx": row["dx"] if pd.notna(row["dx"]) else None,
                "approach": row["approach"] if pd.notna(row["approach"]) else None,
                "position": row["position"] if pd.notna(row["position"]) else None,
                "ane_type": row["ane_type"] if pd.notna(row["ane_type"]) else None,
                "emop": bool(row["emop"]),
                "duration_min": dur,
                "preop_htn": bool(row["preop_htn"]),
                "preop_dm": bool(row["preop_dm"]),
                "ecg_anormal": bool(row.get("ecg_anormal", 0)),
                "preop_ecg": row["preop_ecg"] if pd.notna(row.get("preop_ecg")) else None,
                "pft_anormal": bool(row.get("pft_anormal", 0)),
                "preop_pft": row["preop_pft"] if pd.notna(row.get("preop_pft")) else None,
                "cormack": row["cormack"] if pd.notna(row["cormack"]) else None,
                "airway": row["airway"] if pd.notna(row["airway"]) else None,
                "has_aline": bool(row.get("has_aline", 0)),
                "has_cline": bool(row.get("has_cline", 0)),
                "has_transfusion": bool(row.get("has_transfusion", 0)),
                "death_inhosp": bool(row["death_inhosp"]) if pd.notna(row["death_inhosp"]) else False,
                "icu_days": int(row["icu_days"]) if pd.notna(row["icu_days"]) else 0,
            })

        return {"total_matches": total, "cases": results}

    # ════════════════════════════════════════════════════════════
    #  HELPERS
    # ════════════════════════════════════════════════════════════
    def _value_counts(self, df: pd.DataFrame, col: str,
                      label_map: dict | list | None = None) -> list[dict]:
        counts = df[col].dropna().value_counts()
        options = []
        for val, cnt in counts.items():
            label = val
            if isinstance(label_map, dict):
                label = label_map.get(val, str(val))
            elif isinstance(label_map, list):
                label = str(val)
            options.append({"value": str(val), "label": str(label), "count": int(cnt)})
        return options

    def _value_counts_top(self, df: pd.DataFrame, col: str, n: int = 20) -> list[dict]:
        counts = df[col].dropna().value_counts().head(n)
        return [{"value": str(v), "label": str(v), "count": int(c)} for v, c in counts.items()]

    def _asa_counts(self, df: pd.DataFrame) -> list[dict]:
        counts = df["asa_int"].value_counts().sort_index()
        return [
            {"value": str(a), "label": ASA_LABELS.get(a, f"ASA {a}"), "count": int(c)}
            for a, c in counts.items() if a != 0
        ]

    def _bmi_counts(self, df: pd.DataFrame) -> list[dict]:
        bmi = df["bmi"].dropna()
        return [
            {"value": "underweight", "label": "Maigreur (IMC < 18.5)", "count": int((bmi < 18.5).sum())},
            {"value": "normal", "label": "Normal (18.5-25)", "count": int(((bmi >= 18.5) & (bmi < 25)).sum())},
            {"value": "overweight", "label": "Surpoids (25-30)", "count": int(((bmi >= 25) & (bmi < 30)).sum())},
            {"value": "obese", "label": "Obésité (IMC ≥ 30)", "count": int((bmi >= 30).sum())},
        ]

    def _range_desc(self, df: pd.DataFrame, col: str, label: str, unit: str) -> dict:
        s = df[col].dropna()
        if s.empty:
            return {"label": label, "type": "range", "unit": unit,
                    "min": 0, "max": 0, "mean": 0, "q25": 0, "q75": 0,
                    "available": 0, "filter_key": col}
        return {
            "label": label,
            "type": "range",
            "unit": unit,
            "min": round(float(s.min()), 2),
            "max": round(float(s.max()), 2),
            "mean": round(float(s.mean()), 2),
            "q25": round(float(s.quantile(0.25)), 2),
            "q75": round(float(s.quantile(0.75)), 2),
            "available": int(len(s)),
            "filter_key": col,
        }
