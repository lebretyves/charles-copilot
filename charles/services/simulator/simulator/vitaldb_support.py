from __future__ import annotations

import math
import os
from typing import Any

import pandas as pd


def load_vitaldb_patient_info(vitaldb_dir: str, caseid: int, logger) -> dict[str, Any]:
    csv_path = os.path.join(os.path.dirname(vitaldb_dir), "clinical_metadata.csv")
    if not os.path.exists(csv_path):
        logger.warning("clinical_metadata.csv introuvable: %s", csv_path)
        return {}

    try:
        df = pd.read_csv(csv_path)
        row = df[df["caseid"] == caseid]
        if row.empty:
            return {}
        record = row.iloc[0]

        def value(column: str):
            field = record.get(column)
            if field is None or (isinstance(field, float) and math.isnan(field)):
                return None
            return field

        def value_int(column: str):
            field = value(column)
            return int(field) if field is not None else None

        def value_float(column: str, decimals: int = 1):
            field = value(column)
            return round(float(field), decimals) if field is not None else None

        antecedents_parts: list[str] = []
        if value("preop_htn") == 1:
            antecedents_parts.append("HTA")
        if value("preop_dm") == 1:
            antecedents_parts.append("Diabete")
        antecedents = ", ".join(antecedents_parts) if antecedents_parts else "Aucun note"

        bilan = {}
        for column, label in [
            ("preop_hb", "Hb"),
            ("preop_plt", "Plq"),
            ("preop_cr", "Creat"),
            ("preop_na", "Na"),
            ("preop_k", "K"),
            ("preop_gluc", "Glyc"),
            ("preop_alb", "Alb"),
            ("preop_pt", "TP"),
            ("preop_aptt", "TCA"),
        ]:
            field = value_float(column)
            if field is not None:
                bilan[label] = field

        gds = {}
        for column, label in [
            ("preop_ph", "pH"),
            ("preop_pao2", "PaO2"),
            ("preop_paco2", "PaCO2"),
            ("preop_hco3", "HCO3"),
            ("preop_be", "BE"),
            ("preop_sao2", "SaO2"),
        ]:
            field = value_float(column, 2)
            if field is not None:
                gds[label] = field

        perop = {}
        for column, label in [
            ("intraop_ebl", "Saignement mL"),
            ("intraop_uo", "Diurese mL"),
            ("intraop_crystalloid", "Cristalloides mL"),
            ("intraop_colloid", "Colloides mL"),
            ("intraop_rbc", "CGR"),
            ("intraop_ffp", "PFC"),
        ]:
            field = value_float(column, 0)
            if field is not None and field > 0:
                perop[label] = int(field)

        drogues = {}
        for column, label in [
            ("intraop_ppf", "Propofol mg"),
            ("intraop_ftn", "Fentanyl ug"),
            ("intraop_mdz", "Midazolam mg"),
            ("intraop_rocu", "Rocuronium mg"),
            ("intraop_vecu", "Vecuronium mg"),
            ("intraop_eph", "Ephedrine mg"),
            ("intraop_phe", "Phenylephrine ug"),
            ("intraop_epi", "Adrenaline ug"),
            ("intraop_ca", "Calcium mg"),
        ]:
            field = value_float(column, 0)
            if field is not None and field > 0:
                drogues[label] = int(field)

        return {
            "age": value_int("age"),
            "sex": value("sex"),
            "weight": value_float("weight"),
            "height": value_float("height"),
            "imc": value_float("bmi"),
            "asa": value_int("asa"),
            "emop": bool(value("emop")),
            "department": value("department"),
            "optype": value("optype"),
            "dx": value("dx"),
            "opname": value("opname"),
            "approach": value("approach"),
            "position": value("position"),
            "ane_type": value("ane_type"),
            "antecedents": antecedents,
            "preop_htn": bool(value("preop_htn")),
            "preop_dm": bool(value("preop_dm")),
            "preop_ecg": value("preop_ecg"),
            "preop_pft": value("preop_pft"),
            "cormack": value("cormack"),
            "airway": value("airway"),
            "tubesize": value_float("tubesize"),
            "iv1": value("iv1"),
            "iv2": value("iv2"),
            "aline1": value("aline1"),
            "cline1": value("cline1"),
            "mallampati": None,
            "allergies": None,
            "traitement": None,
            "bilan_preop": bilan if bilan else None,
            "gds_preop": gds if gds else None,
            "perop": perop if perop else None,
            "drogues": drogues if drogues else None,
            "icu_days": value_int("icu_days"),
            "death_inhosp": bool(value("death_inhosp")),
        }
    except Exception as exc:
        logger.warning("Erreur chargement metadata case %d: %s", caseid, exc)
        return {}
