"""Scenario definitions and simulated room state for CHARLES."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

@dataclass
class PhysioState:
    """État physiologique d'un patient simulé."""
    # Hémodynamique
    hr: float = 72.0        # bpm
    pas: float = 125.0      # mmHg
    pad: float = 72.0       # mmHg
    pam: float = 90.0       # mmHg
    # Respiratoire
    spo2: float = 99.0      # %
    etco2: float = 35.0     # mmHg
    fr: float = 14.0        # /min
    # Température
    temp: float = 36.8      # °C
    # Ventilateur
    vent_mode: str = "VACI"
    vt: float = 480.0       # mL
    mv: float = 6.7         # L/min
    ppeak: float = 18.0     # cmH2O
    pplat: float = 14.0     # cmH2O
    peep: float = 5.0       # cmH2O
    fio2: float = 50.0      # %
    # BIS
    bis: float = 45.0       # index
    sqi: float = 95.0       # %
    emg: float = 28.0       # dB
    sr: float = 0.0         # %
    # AIVOC Propofol
    propofol_target: float = 3.5       # µg/mL
    propofol_plasma: float = 3.4       # µg/mL
    propofol_effect: float = 3.2       # µg/mL
    propofol_rate: float = 180.0       # mL/h
    # AIVOC Remifentanil
    remi_target: float = 4.0           # ng/mL
    remi_plasma: float = 3.8           # ng/mL
    remi_effect: float = 3.5           # ng/mL
    remi_rate: float = 25.0            # mL/h

    def compute_pam(self):
        self.pam = round(self.pad + (self.pas - self.pad) / 3, 1)

    def add_noise(self):
        """Bruit physiologique réaliste."""
        self.hr += np.random.normal(0, 1.5)
        self.pas += np.random.normal(0, 2.0)
        self.pad += np.random.normal(0, 1.5)
        self.spo2 += np.random.normal(0, 0.3)
        self.etco2 += np.random.normal(0, 0.8)
        self.fr += np.random.normal(0, 0.5)
        self.temp += np.random.normal(0, 0.02)
        self.bis += np.random.normal(0, 2.0)
        self.sqi += np.random.normal(0, 1.0)
        self.propofol_plasma += np.random.normal(0, 0.1)
        self.propofol_effect += np.random.normal(0, 0.08)
        self.remi_plasma += np.random.normal(0, 0.15)
        self.remi_effect += np.random.normal(0, 0.1)

        # Clamp
        self.hr = np.clip(self.hr, 30, 200)
        self.pas = np.clip(self.pas, 50, 250)
        self.pad = np.clip(self.pad, 25, 150)
        self.spo2 = np.clip(self.spo2, 60, 100)
        self.etco2 = np.clip(self.etco2, 10, 80)
        self.fr = np.clip(self.fr, 4, 45)
        self.temp = np.clip(self.temp, 33, 42)
        self.bis = np.clip(self.bis, 0, 100)
        self.sqi = np.clip(self.sqi, 0, 100)
        self.sr = np.clip(self.sr, 0, 100)
        self.vt = np.clip(self.vt, 100, 1000)
        self.compute_pam()


# ══════════════════════════════════════════════════════════════
#  SCÉNARIOS CLINIQUES
# ══════════════════════════════════════════════════════════════

class Scenario:
    """Classe de base pour les scénarios."""
    name: str = "base"
    description: str = ""
    duration_steps: int = 120  # 10 minutes (120 x 5s)

    def __init__(self):
        self.step = 0

    def apply(self, state: PhysioState) -> str:
        """Applique le scénario au pas courant. Retourne la phase."""
        self.step += 1
        return "stable"


class NormalScenario(Scenario):
    """Cholécystectomie coelioscopique sans complication — ASA 1, 45 ans, H, 75kg."""
    name = "normal"
    description = "Cholécystectomie coelioscopique — patient stable ASA 1"
    duration_steps = 240  # 20 minutes

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        # Phase 1 : entretien stable (0–5 min)
        if self.step < 60:
            state.hr += np.random.normal(0, 0.5) * 0.1
            state.pas += np.random.normal(0, 0.5) * 0.1
            return "entretien_stable"
        # Phase 2 : insufflation CO2 (5–8 min) — légère hausse PA, EtCO2
        elif self.step < 96:
            state.pas += 0.3
            state.pad += 0.2
            state.etco2 += 0.15
            state.hr -= 0.1  # réflexe vagal léger
            state.ppeak += 0.1
            return "insufflation_co2"
        # Phase 3 : chirurgie (8–15 min) — stable
        elif self.step < 180:
            state.temp -= 0.003  # hypothermie légère progressive
            return "chirurgie"
        # Phase 4 : exsufflation + réveil (15–20 min)
        else:
            state.bis += 0.5
            state.hr += 0.3
            state.pas += 0.4
            state.propofol_target = max(1.5, state.propofol_target - 0.02)
            state.propofol_plasma = max(1.0, state.propofol_plasma - 0.03)
            state.remi_target = max(1.0, state.remi_target - 0.03)
            return "reveil"


class HypotensionScenario(Scenario):
    """Hypotension progressive post-induction — typique du sujet âgé."""
    name = "hypotension"
    description = "Hypotension progressive post-induction — ASA 2, 72 ans"
    duration_steps = 180

    def __init__(self):
        super().__init__()
        # Patient âgé, HTA traitée
        self.initial_pas = 145

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.hr = 68
            state.pas = self.initial_pas
            state.pad = 82
            state.temp = 36.5

        # Phase 1 : stable post-induction (0–2 min)
        if self.step < 24:
            return "post_induction_stable"
        # Phase 2 : chute progressive (2–6 min)
        elif self.step < 72:
            state.pas -= 0.8  # perd ~40 mmHg en 4 min
            state.pad -= 0.4
            state.pam -= 0.5
            state.hr += 0.3   # tachycardie compensatrice
            return "hypotension_progressive"
        # Phase 3 : hypotension sévère (6–10 min)
        elif self.step < 120:
            state.pas = max(70, state.pas - 0.2)
            state.hr = min(120, state.hr + 0.2)
            state.spo2 -= 0.05
            return "hypotension_severe"
        # Phase 4 : correction (éphédrine/néosynéphrine) (10–15 min)
        else:
            state.pas += 1.2
            state.pad += 0.6
            state.hr -= 0.5
            state.spo2 += 0.1
            return "correction_vasopresseurs"


class DesaturationScenario(Scenario):
    """Intubation difficile avec désaturation — Cormack 3."""
    name = "desaturation"
    description = "Intubation difficile — désaturation transitoire"
    duration_steps = 120

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        # Phase 1 : pré-oxygénation OK (0–1 min)
        if self.step < 12:
            state.spo2 = 100
            state.fio2 = 100
            return "preox"
        # Phase 2 : tentative intubation — apnée (1–3 min)
        elif self.step < 36:
            state.spo2 -= 0.8  # chute ~20% en 2 min
            state.hr += 0.8
            state.pas += 1.0
            state.etco2 += 0.5
            state.bis += 0.3   # allègement
            return "tentative_intubation"
        # Phase 3 : ventilation au masque (3–5 min)
        elif self.step < 60:
            state.spo2 += 0.5
            state.hr -= 0.3
            state.etco2 -= 0.2
            return "ventilation_masque"
        # Phase 4 : 2ème tentative réussie (5–7 min)
        elif self.step < 84:
            state.spo2 += 0.3
            state.etco2 = 35 + np.random.normal(0, 1)
            state.fr = 14
            return "intubation_reussie"
        # Phase 5 : stabilisation (7–10 min)
        else:
            state.spo2 = min(99, state.spo2 + 0.1)
            state.hr -= 0.2
            state.pas -= 0.3
            return "stabilisation"


class AnaphylaxieScenario(Scenario):
    """Réaction anaphylactique peropératoire — grade II/III."""
    name = "anaphylaxie"
    description = "Anaphylaxie peropératoire — bronchospasme + collapsus"
    duration_steps = 180

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        # Phase 1 : stable (0–2 min)
        if self.step < 24:
            return "stable_pre_event"
        # Phase 2 : début anaphylaxie — brutal (2–4 min)
        elif self.step < 48:
            state.hr += 2.0       # tachycardie brutale
            state.pas -= 3.0      # collapsus
            state.pad -= 1.5
            state.spo2 -= 0.5     # bronchospasme
            state.ppeak += 1.5    # hausse pressions voies aériennes
            state.etco2 += 0.8
            state.temp += 0.05
            return "anaphylaxie_onset"
        # Phase 3 : anaphylaxie sévère (4–8 min)
        elif self.step < 96:
            state.hr = min(160, state.hr + 0.5)
            state.pas = max(55, state.pas - 0.5)
            state.spo2 = max(80, state.spo2 - 0.3)
            state.ppeak = min(45, state.ppeak + 0.3)
            state.etco2 = max(15, state.etco2 - 0.5)  # hyperventilation
            return "anaphylaxie_severe"
        # Phase 4 : traitement (adrénaline) (8–12 min)
        elif self.step < 144:
            state.hr -= 1.0
            state.pas += 2.0
            state.pad += 1.0
            state.spo2 += 0.4
            state.ppeak -= 0.5
            return "traitement_adrenaline"
        # Phase 5 : récupération
        else:
            state.hr -= 0.3
            state.pas += 0.5
            state.spo2 = min(98, state.spo2 + 0.2)
            return "recuperation"


class HemorragieScenario(Scenario):
    """Hémorragie peropératoire progressive — chirurgie abdominale."""
    name = "hemorragie"
    description = "Hémorragie peropératoire — pertes sanguines progressives 800mL"
    duration_steps = 240

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        # Phase 1 : chirurgie stable (0–5 min)
        if self.step < 60:
            return "chirurgie_stable"
        # Phase 2 : saignement débutant (5–10 min)
        elif self.step < 120:
            state.hr += 0.3
            state.pas -= 0.3
            state.pad -= 0.15
            return "saignement_modere"
        # Phase 3 : hémorragie active (10–15 min)
        elif self.step < 180:
            state.hr += 0.6       # tachycardie compensatrice
            state.pas -= 0.8      # chute PA
            state.pad -= 0.4
            state.spo2 -= 0.05    # léger
            state.temp -= 0.01    # refroidissement
            state.etco2 -= 0.1    # baisse débit cardiaque
            return "hemorragie_active"
        # Phase 4 : remplissage + transfusion (15–20 min)
        else:
            state.hr -= 0.4
            state.pas += 0.8
            state.pad += 0.4
            state.spo2 += 0.1
            return "remplissage_transfusion"


class BronchospasmScenario(Scenario):
    """Bronchospasme peropératoire — patiente asthmatique, terrain atopique."""
    name = "bronchospasme"
    description = "Bronchospasme peropératoire — terrain atopique, curare"
    duration_steps = 180

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.spo2 = 99.0
            state.etco2 = 35.0
            state.ppeak = 18.0
            state.fr = 14.0
        # Phase 1 : maintenance stable (0–2 min)
        if self.step < 24:
            return "maintenance_stable"
        # Phase 2 : bronchospasme onset (2–5 min) — sibilants, résistances↑
        elif self.step < 60:
            state.spo2 -= 0.4          # désaturation progressive
            state.etco2 += 0.6         # air trapping → EtCO2↑
            state.ppeak += 1.2         # pressions voies aériennes↑↑
            state.pplat += 0.4
            state.fr += 0.3
            state.hr += 0.8            # tachycardie réflexe
            state.pas += 0.5
            return "bronchospasme_onset"
        # Phase 3 : bronchospasme sévère (5–8 min)
        elif self.step < 96:
            state.spo2 = max(82, state.spo2 - 0.3)
            state.etco2 = min(60, state.etco2 + 0.4)
            state.ppeak = min(50, state.ppeak + 0.5)
            state.hr = min(140, state.hr + 0.4)
            state.pas = max(85, state.pas - 0.3)   # effet obstructif
            return "bronchospasme_severe"
        # Phase 4 : traitement sévoflurane + salbutamol (8–12 min)
        elif self.step < 144:
            state.spo2 = min(98, state.spo2 + 0.5)
            state.etco2 = max(35, state.etco2 - 0.7)
            state.ppeak = max(18, state.ppeak - 1.0)
            state.hr -= 0.6
            state.pas += 0.4
            return "traitement_bronchodilatateur"
        # Phase 5 : récupération (12–15 min)
        else:
            state.spo2 = min(99, state.spo2 + 0.2)
            state.etco2 = max(35, state.etco2 - 0.3)
            state.ppeak = max(18, state.ppeak - 0.3)
            state.hr -= 0.3
            return "recuperation_bronchospasme"


class BradycardieScenario(Scenario):
    """Bradycardie vagale sévère — rachianesthésie haute, β-bloquant."""
    name = "bradycardie"
    description = "Bradycardie sévère — bloc sympathique haut + β-bloquant"
    duration_steps = 180

    def __init__(self):
        super().__init__()

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.hr = 62.0
            state.pas = 130.0
            state.pad = 75.0
        # Phase 1 : stable post-rachi (0–2 min)
        if self.step < 24:
            return "stable_post_induction"
        # Phase 2 : bloc sympathique montant (2–5 min)
        elif self.step < 60:
            state.hr -= 0.7           # bradycardie progressive
            state.pas -= 0.6
            state.pad -= 0.3
            return "bradycardie_progressive"
        # Phase 3 : bradycardie sévère < 40 bpm (5–8 min)
        elif self.step < 96:
            state.hr = max(28, state.hr - 0.5)
            state.pas = max(65, state.pas - 0.5)
            state.spo2 -= 0.1
            state.etco2 -= 0.3        # bas débit cardiaque
            return "bradycardie_severe"
        # Phase 4 : atropine 1 mg IVD (8–12 min)
        elif self.step < 144:
            state.hr = min(90, state.hr + 1.5)
            state.pas = min(120, state.pas + 1.2)
            state.pad += 0.6
            state.spo2 = min(98, state.spo2 + 0.2)
            return "traitement_atropine"
        # Phase 5 : stabilisation (12–15 min)
        else:
            state.hr += np.random.normal(0, 0.5) * 0.2
            state.pas += 0.2
            return "stabilisation_bradycardie"


class CriseHypertensiveScenario(Scenario):
    """Crise hypertensive peropératoire — analgésie insuffisante, HTA préop."""
    name = "crise_hypertensive"
    description = "Crise hypertensive — stimulus nociceptif + HTA non équilibrée"
    duration_steps = 180

    def __init__(self):
        super().__init__()

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.hr = 75.0
            state.pas = 145.0        # HTA de base
            state.pad = 85.0
            state.bis = 50.0
        # Phase 1 : entretien (0–3 min)
        if self.step < 36:
            state.pas += 0.2
            return "entretien_hta"
        # Phase 2 : stimulus nociceptif — incision profonde (3–6 min)
        elif self.step < 72:
            state.pas += 1.5         # poussée hypertensive brutale
            state.pad += 0.8
            state.hr += 0.8          # tachycardie sympathique
            state.bis += 0.4         # allègement anesthésie
            return "stimulus_nociceptif"
        # Phase 3 : crise hypertensive sévère (6–10 min)
        elif self.step < 120:
            state.pas = min(220, state.pas + 0.3)
            state.hr = min(115, state.hr + 0.2)
            state.etco2 += 0.1
            return "crise_hypertensive"
        # Phase 4 : traitement nicardipine + rémifentanil (10–13 min)
        elif self.step < 156:
            state.pas -= 2.5
            state.pad -= 1.2
            state.hr -= 0.8
            state.bis -= 0.3
            return "traitement_antihypertenseur"
        # Phase 5 : normalisation (13–15 min)
        else:
            state.pas -= 0.5
            state.hr -= 0.3
            return "normalisation_pa"


class HyperthermiesMaligneScenario(Scenario):
    """Hyperthermie maligne — AG avec halogénés, sujet susceptible."""
    name = "hyperthermie_maligne"
    description = "Hyperthermie maligne — halogéné + susceptibilité génétique"
    duration_steps = 240

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.temp = 36.8
            state.etco2 = 35.0
            state.hr = 70.0
            state.emg = 30.0         # rigidité musculaire (EMG↑)
        # Phase 1 : chirurgie stable (0–5 min)
        if self.step < 60:
            return "chirurgie_hm_stable"
        # Phase 2 : signes précoces — EtCO2↑ + rigidité + tachy (5–10 min)
        elif self.step < 120:
            state.etco2 += 0.4       # hyperproduction CO2 musculaire
            state.hr += 0.5
            state.temp += 0.02
            state.emg += 0.5         # contracture musculaire
            state.bis += 0.2
            return "hm_signes_precoces"
        # Phase 3 : crise franche (10–15 min) — temp↑↑ + HR↑↑ + EtCO2↑↑
        elif self.step < 180:
            state.temp = min(42.0, state.temp + 0.08)  # fièvre très rapide
            state.etco2 = min(80, state.etco2 + 0.6)
            state.hr = min(160, state.hr + 0.8)
            state.spo2 -= 0.1
            state.pas += 0.5
            return "hm_crise"
        # Phase 4 : dantrolène + arrêt halogéné + refroidissement (15–20 min)
        else:
            state.temp = max(37.5, state.temp - 0.06)  # refroidissement lent
            state.etco2 = max(38, state.etco2 - 0.8)
            state.hr -= 0.8
            state.spo2 = min(99, state.spo2 + 0.2)
            return "traitement_dantrolene"


class EmbolieGazeuseScenario(Scenario):
    """Embolie gazeuse veineuse — neurochirurgie position assise."""
    name = "embolie_gazeuse"
    description = "Embolie gazeuse — voie veineuse ouverte + position assise"
    duration_steps = 200

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.etco2 = 35.0
            state.hr = 68.0
            state.pas = 120.0
            state.spo2 = 99.0
        # Phase 1 : neurochirurgie stable (0–3 min)
        if self.step < 36:
            return "neurochirurgie_stable"
        # Phase 2 : embolie gazeuse — EtCO2↓ brutal (3–6 min)
        elif self.step < 72:
            state.etco2 -= 1.2       # chute EtCO2 brutale (obstruction)
            state.hr += 1.0          # tachycardie réflexe
            state.pas -= 0.8
            state.spo2 -= 0.3
            return "embolie_onset"
        # Phase 3 : hémodynamique compromise (6–10 min)
        elif self.step < 120:
            state.etco2 = max(15, state.etco2 - 0.5)
            state.pas = max(70, state.pas - 0.8)
            state.hr = min(140, state.hr + 0.5)
            state.spo2 = max(85, state.spo2 - 0.3)
            return "embolie_severe"
        # Phase 4 : traitement — position, aspiration, FiO2 100% (10–14 min)
        elif self.step < 168:
            state.etco2 = min(35, state.etco2 + 0.8)
            state.pas = min(110, state.pas + 1.0)
            state.hr -= 0.8
            state.spo2 = min(97, state.spo2 + 0.5)
            state.fio2 = 100.0
            return "traitement_embolie"
        # Phase 5 : récupération (14–17 min)
        else:
            state.etco2 = min(35, state.etco2 + 0.2)
            state.hr -= 0.3
            return "recuperation_embolie"


class PneumothoraxScenario(Scenario):
    """Pneumothorax sous tension — voie centrale sous-clavière, BPCO."""
    name = "pneumothorax"
    description = "Pneumothorax sous tension — après voie centrale sous-clavière"
    duration_steps = 200

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.ppeak = 18.0
            state.spo2 = 97.0
            state.hr = 72.0
            state.pas = 125.0
        # Phase 1 : chirurgie stable (0–3 min)
        if self.step < 36:
            return "stable_pre_pneumo"
        # Phase 2 : pneumothorax — Ppeak↑ + SpO2↓ (3–6 min)
        elif self.step < 72:
            state.ppeak += 1.0       # résistance unilatérale↑
            state.spo2 -= 0.5
            state.hr += 0.7
            state.pas -= 0.4
            return "pneumothorax_onset"
        # Phase 3 : mise en tension (6–10 min) — déviation médiastin
        elif self.step < 120:
            state.ppeak = min(55, state.ppeak + 0.8)
            state.spo2 = max(82, state.spo2 - 0.6)
            state.pas = max(65, state.pas - 1.0)  # retour veineux compromis
            state.hr = min(145, state.hr + 0.8)
            state.etco2 -= 0.3
            return "pneumothorax_tension"
        # Phase 4 : exsufflation à l'aiguille → drain (10–14 min)
        elif self.step < 168:
            state.ppeak = max(20, state.ppeak - 1.5)
            state.spo2 = min(96, state.spo2 + 0.8)
            state.pas = min(115, state.pas + 1.2)
            state.hr -= 1.0
            state.etco2 = min(35, state.etco2 + 0.4)
            return "exsufflation_drain"
        # Phase 5 : stabilisation (14–17 min)
        else:
            state.hr -= 0.3
            state.spo2 = min(97, state.spo2 + 0.2)
            return "stabilisation_pneumo"


class ReveilPeropScenario(Scenario):
    """Réveil peropératoire (awareness) — césarienne AG, curares."""
    name = "reveil_perop"
    description = "Awareness peropératoire — allègement anesthésie sous curares"
    duration_steps = 180

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.bis = 48.0
            state.hr = 68.0
            state.pas = 115.0
            state.propofol_target = 3.5
            state.propofol_effect = 3.2
        # Phase 1 : AG correcte (0–3 min)
        if self.step < 36:
            return "ag_correcte"
        # Phase 2 : allègement progressif — BIS↑ (3–6 min)
        elif self.step < 72:
            state.bis += 0.5         # BIS monte progressivement
            state.hr += 0.5          # tachycardie sympathique
            state.pas += 0.8
            state.propofol_effect -= 0.02
            return "allègement_anesthesie"
        # Phase 3 : awareness — BIS > 70, réaction sympathique (6–9 min)
        elif self.step < 108:
            state.bis = min(85, state.bis + 0.6)
            state.hr = min(125, state.hr + 0.8)
            state.pas = min(185, state.pas + 1.2)   # HTA de réveil
            state.pad += 0.6
            return "awareness_active"
        # Phase 4 : approfondissement propofol + opiacé (9–12 min)
        elif self.step < 144:
            state.bis -= 1.5
            state.hr -= 1.0
            state.pas -= 2.0
            state.propofol_target = min(4.5, state.propofol_target + 0.1)
            state.propofol_effect = min(4.2, state.propofol_effect + 0.08)
            return "approfondissement_ag"
        # Phase 5 : sédation récupérée (12–15 min)
        else:
            state.bis = max(45, state.bis - 0.4)
            state.hr -= 0.3
            state.pas -= 0.5
            return "sedation_recuperee"


class ACRScenario(Scenario):
    """Arrêt cardiaque peropératoire — patient cardiaque à haut risque."""
    name = "acr"
    description = "Arrêt cardiaque peropératoire — FV sur ischémie myocardique"
    duration_steps = 240

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.hr = 78.0
            state.pas = 120.0
            state.spo2 = 97.0
            state.etco2 = 34.0
        # Phase 1 : chirurgie stable (0–3 min)
        if self.step < 36:
            return "preacr_stable"
        # Phase 2 : signes précurseurs (3–5 min) — ischémie
        elif self.step < 60:
            state.hr -= 0.8          # bradycardie pré-ACR
            state.pas -= 1.5
            state.etco2 -= 0.5
            state.spo2 -= 0.2
            return "preacr_deterioration"
        # Phase 3 : ACR — asystolie / FV (5–8 min)
        elif self.step < 96:
            state.hr = max(0, state.hr - 4.0)
            state.pas = max(0, state.pas - 8.0)
            state.pad = max(0, state.pad - 4.0)
            state.spo2 = max(60, state.spo2 - 1.0)
            state.etco2 = max(5, state.etco2 - 2.0)
            state.bis = max(0, state.bis - 3.0)
            return "acr_asystolie"
        # Phase 4 : RCP + adrénaline (8–14 min)
        elif self.step < 168:
            # Pendant MCE : ondulations PA, FC artificielle
            cycle = self.step % 12
            if cycle < 6:
                state.pas = 60 + np.random.normal(0, 5)
                state.hr = 100 + np.random.normal(0, 10)  # FC MCE
            else:
                state.pas = 20 + np.random.normal(0, 3)
                state.hr = 0
            state.etco2 = min(25, state.etco2 + 0.3)     # MCE efficace si EtCO2↑
            state.spo2 = min(85, state.spo2 + 0.2)
            return "rcp_en_cours"
        # Phase 5 : RACS — Retour à la Circulation Spontanée (14–20 min)
        else:
            state.hr = min(95, state.hr + 2.0)
            state.pas = min(105, state.pas + 3.0)
            state.pad = min(60, state.pad + 1.5)
            state.etco2 = min(35, state.etco2 + 0.5)
            state.spo2 = min(94, state.spo2 + 0.5)
            state.bis = min(40, state.bis + 1.0)
            return "racs"


class TachycardieScenario(Scenario):
    """Tachycardie peropératoire — analgésie insuffisante + stimulus nociceptif."""
    name = "tachycardie"
    description = "Tachycardie — analgésie insuffisante, diagnostic différentiel IADE"
    duration_steps = 180

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.hr = 78.0
            state.pas = 120.0
            state.bis = 52.0
        # Phase 1 : entretien stable (0–3 min)
        if self.step < 36:
            return "entretien_tachy_stable"
        # Phase 2 : stimulus nociceptif — allègement (3–6 min)
        elif self.step < 72:
            state.hr += 0.9            # tachycardie rapide
            state.pas += 0.6
            state.bis += 0.4           # allègement
            state.etco2 += 0.2
            return "stimulus_douloureux"
        # Phase 3 : tachycardie persistante > 120 (6–10 min)
        elif self.step < 120:
            state.hr = min(140, state.hr + 0.3)
            state.spo2 -= 0.05
            state.etco2 += 0.1
            return "tachycardie_persistante"
        # Phase 4 : bolus rémifentanil + approfondissement (10–13 min)
        elif self.step < 156:
            state.hr -= 1.2
            state.pas -= 0.8
            state.bis -= 0.5
            state.etco2 -= 0.2
            return "traitement_analgesie"
        # Phase 5 : normalisation (13–15 min)
        else:
            state.hr -= 0.3
            state.pas -= 0.2
            return "normalisation_tachy"


class HypothermieScenario(Scenario):
    """Hypothermie peropératoire progressive — chirurgie longue, patient âgé."""
    name = "hypothermie"
    description = "Hypothermie peropératoire — chirurgie abdominale longue > 3h"
    duration_steps = 300

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.temp = 36.8
            state.hr = 65.0
            state.pas = 125.0
        # Phase 1 : début chirurgie (0–5 min) — légère déperdition
        if self.step < 60:
            state.temp -= 0.005
            return "chirurgie_debut"
        # Phase 2 : hypothermie modérée (5–15 min) — T° < 36
        elif self.step < 180:
            state.temp -= 0.008       # refroidissement progressif
            state.hr -= 0.1           # bradycardie légère liée au froid
            state.pam -= 0.05
            state.fr -= 0.02
            return "hypothermie_moderee"
        # Phase 3 : hypothermie sévère (15–20 min) — T° < 35
        elif self.step < 240:
            state.temp = max(33.5, state.temp - 0.01)
            state.hr = max(42, state.hr - 0.2)
            state.pad -= 0.1
            state.bis -= 0.1          # surdosage relatif agents
            return "hypothermie_severe"
        # Phase 4 : réchauffement actif — couverture chauffante, solutés chauds (20–25 min)
        else:
            state.temp = min(36.5, state.temp + 0.015)
            state.hr = min(68, state.hr + 0.2)
            state.pam = min(85, state.pam + 0.1)
            return "rechauffement_actif"


class BurstSuppressionScenario(Scenario):
    """Burst suppression — surdosage propofol/halogéné, sujet âgé fragile."""
    name = "burst_suppression"
    description = "Burst suppression — surdosage anesthésique, BIS < 20"
    duration_steps = 200

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.bis = 55.0
            state.sr = 0.0
            state.hr = 62.0
            state.pas = 118.0
            state.propofol_target = 3.5
            state.propofol_effect = 3.2
        # Phase 1 : AG correcte (0–2 min)
        if self.step < 24:
            return "ag_correcte_bis"
        # Phase 2 : approfondissement excessif (2–5 min)
        elif self.step < 60:
            state.bis -= 0.8
            state.sr += 0.3            # SR commence à monter
            state.hr -= 0.4
            state.pas -= 0.6
            state.propofol_target = min(6.0, state.propofol_target + 0.05)
            state.propofol_effect = min(5.5, state.propofol_effect + 0.04)
            return "approfondissement_excessif"
        # Phase 3 : burst suppression franche (5–9 min) — BIS < 20, SR > 50%
        elif self.step < 108:
            state.bis = max(8, state.bis - 0.5)
            state.sr = min(75, state.sr + 0.8)
            state.hr = max(38, state.hr - 0.3)
            state.pas = max(72, state.pas - 0.5)   # hypotension surdosage
            state.pad = max(40, state.pad - 0.3)
            return "burst_suppression_active"
        # Phase 4 : réduction propofol + alerte IADE (9–13 min)
        elif self.step < 156:
            state.bis = min(40, state.bis + 1.0)
            state.sr = max(0, state.sr - 1.5)
            state.hr = min(65, state.hr + 0.5)
            state.pas = min(110, state.pas + 0.8)
            state.propofol_target = max(2.5, state.propofol_target - 0.08)
            state.propofol_effect = max(2.2, state.propofol_effect - 0.06)
            return "reduction_hypnotique"
        # Phase 5 : BIS récupéré (13–17 min)
        else:
            state.bis = min(52, state.bis + 0.3)
            state.sr = max(0, state.sr - 0.5)
            state.hr = min(68, state.hr + 0.2)
            return "bis_recupere"


class IntubationDifficileScenario(Scenario):
    """Intubation difficile Plan A→B→C→CICO — Mallampati 4, obésité morbide."""
    name = "intubation_difficile"
    description = "Intubation difficile — CICO (can't intubate can't oxygenate)"
    duration_steps = 180

    def apply(self, state: PhysioState) -> str:
        self.step += 1
        if self.step == 1:
            state.spo2 = 100.0
            state.fio2 = 100.0
            state.hr = 72.0
            state.etco2 = 0.0         # pas d'intubation encore
        # Phase 1 : pré-oxygénation 3 min FiO2 100% (0–3 min)
        if self.step < 36:
            state.spo2 = min(100, state.spo2 + 0.05)
            state.hr += 0.2            # anxiété peropératoire
            return "preox_id"
        # Phase 2 : Plan A — laryngoscopie directe, échec (3–5 min)
        elif self.step < 60:
            state.spo2 -= 1.2          # apnée + effort laryngoscopie
            state.hr += 1.0
            state.pas += 1.2
            state.etco2 = 0.0          # pas de capno sans intubation
            return "plan_a_echec"
        # Phase 3 : Plan B — masque laryngé 2e génération (5–7 min)
        elif self.step < 84:
            state.spo2 += 0.5          # ventilation partielle
            state.hr -= 0.3
            state.etco2 = 12 + self.step * 0.2  # capno progressif
            return "plan_b_ml"
        # Phase 4 : Plan B insuffisant — désaturation (7–9 min)
        elif self.step < 108:
            state.spo2 -= 0.8          # ventilation ML insuffisante (obèse)
            state.hr += 0.6
            state.pas -= 0.4
            state.etco2 = max(10, state.etco2 - 0.5)
            return "plan_b_insuffisant"
        # Phase 5 : CICO — Masque facial 2 mains + Guedel (9–11 min)
        elif self.step < 132:
            state.spo2 -= 0.5          # SpO2 en chute < 80%
            state.hr = min(155, state.hr + 0.8)
            state.spo2 = max(62, state.spo2)
            state.etco2 = 0.0
            return "cico_masque_facial"
        # Phase 6 : plan D — cricothyroïdotomie au scalpel (11–13 min)
        elif self.step < 156:
            state.spo2 = min(90, state.spo2 + 1.5)  # remontée lente
            state.etco2 = min(28, (self.step - 132) * 1.0)
            state.hr -= 1.0
            return "cricothyroidotomie"
        # Phase 7 : sécurisation voie aérienne (13–15 min)
        else:
            state.spo2 = min(96, state.spo2 + 0.5)
            state.etco2 = min(35, state.etco2 + 0.5)
            state.hr -= 0.5
            state.pas -= 0.4
            return "vae_securisee"

SCENARIOS = {
    "normal": NormalScenario,
    "hypotension": HypotensionScenario,
    "desaturation": DesaturationScenario,
    "anaphylaxie": AnaphylaxieScenario,
    "hemorragie": HemorragieScenario,
    "bronchospasme": BronchospasmScenario,
    "bradycardie": BradycardieScenario,
    "crise_hypertensive": CriseHypertensiveScenario,
    "hyperthermie_maligne": HyperthermiesMaligneScenario,
    "embolie_gazeuse": EmbolieGazeuseScenario,
    "pneumothorax": PneumothoraxScenario,
    "reveil_perop": ReveilPeropScenario,
    "acr": ACRScenario,
    "tachycardie": TachycardieScenario,
    "hypothermie": HypothermieScenario,
    "burst_suppression": BurstSuppressionScenario,
    "intubation_difficile": IntubationDifficileScenario,
}


# Labels lisibles pour chaque phase synthétique
PHASE_LABELS = {
    "init": "Initialisation",
    "stable": "Stable",
    "entretien_stable": "Entretien stable",
    "insufflation_co2": "Insufflation CO₂",
    "chirurgie": "Chirurgie",
    "reveil": "Réveil / Émergence",
    "post_induction_stable": "Post-induction stable",
    "hypotension_progressive": "Hypotension progressive",
    "hypotension_severe": "Hypotension sévère",
    "correction_vasopresseurs": "Correction vasopresseurs",
    "preox": "Pré-oxygénation",
    "tentative_intubation": "Tentative intubation",
    "ventilation_masque": "Ventilation au masque",
    "intubation_reussie": "Intubation réussie",
    "stabilisation": "Stabilisation",
    "stable_pre_event": "Stable pré-événement",
    "anaphylaxie_onset": "Anaphylaxie — début",
    "anaphylaxie_severe": "Anaphylaxie sévère",
    "traitement_adrenaline": "Traitement adrénaline",
    "recuperation": "Récupération",
    "chirurgie_stable": "Chirurgie stable",
    "saignement_modere": "Saignement modéré",
    "hemorragie_active": "Hémorragie active",
    "remplissage_transfusion": "Remplissage / Transfusion",
    # Bronchospasme
    "maintenance_stable": "Maintenance stable",
    "bronchospasme_onset": "Bronchospasme — début",
    "bronchospasme_severe": "Bronchospasme sévère",
    "traitement_bronchodilatateur": "Salbutamol / Sévoflurane",
    "recuperation_bronchospasme": "Récupération bronchospasme",
    # Bradycardie
    "bradycardie_progressive": "Bradycardie progressive",
    "bradycardie_severe": "Bradycardie sévère",
    "traitement_atropine": "Atropine IVD",
    "stabilisation_bradycardie": "Stabilisation",
    # Crise hypertensive
    "entretien_hta": "Entretien (HTA)",
    "stimulus_nociceptif": "Stimulus nociceptif",
    "crise_hypertensive": "Crise hypertensive",
    "traitement_antihypertenseur": "Nicardipine / Rémifentanil",
    "normalisation_pa": "Normalisation PA",
    # Hyperthermie maligne
    "chirurgie_hm_stable": "Chirurgie (pré-HM)",
    "hm_signes_precoces": "Signes précoces HM",
    "hm_crise": "Crise d'hyperthermie maligne",
    "traitement_dantrolene": "Dantrolène + refroidissement",
    # Embolie gazeuse
    "neurochirurgie_stable": "Neurochirurgie stable",
    "embolie_onset": "Embolie gazeuse — début",
    "embolie_severe": "Embolie gazeuse sévère",
    "traitement_embolie": "Aspiration / FiO₂ 100%",
    "recuperation_embolie": "Récupération embolie",
    # Pneumothorax
    "stable_pre_pneumo": "Stable (pré-pneumothorax)",
    "pneumothorax_onset": "Pneumothorax — début",
    "pneumothorax_tension": "Pneumothorax sous tension",
    "exsufflation_drain": "Exsufflation / Drain",
    "stabilisation_pneumo": "Stabilisation pneumothorax",
    # Réveil peropératoire
    "ag_correcte": "AG correcte",
    "allègement_anesthesie": "Allègement progressif",
    "awareness_active": "Awareness — réveil perop.",
    "approfondissement_ag": "Approfondissement AG",
    "sedation_recuperee": "Sédation récupérée",
    # ACR
    "preacr_stable": "Stable (pré-ACR)",
    "preacr_deterioration": "Dégradation hémodynamique",
    "acr_asystolie": "ACR — Asystolie",
    "rcp_en_cours": "RCP en cours",
    "racs": "RACS — Retour circulation spontanée",
    # Tachycardie
    "entretien_tachy_stable": "Entretien stable (tachycardie)",
    "stimulus_douloureux": "Stimulus nociceptif — allègement",
    "tachycardie_persistante": "Tachycardie persistante > 120",
    "traitement_analgesie": "Bolus rémifentanil / approfondissement",
    "normalisation_tachy": "Normalisation FC",
    # Hypothermie
    "chirurgie_debut": "Début chirurgie (normothermique)",
    "hypothermie_moderee": "Hypothermie modérée < 36 °C",
    "hypothermie_severe": "Hypothermie sévère < 35 °C",
    "rechauffement_actif": "Réchauffement actif",
    # Burst suppression
    "ag_correcte_bis": "AG correcte — BIS 40-60",
    "approfondissement_excessif": "Surdosage — approfondissement excessif",
    "burst_suppression_active": "Burst suppression — BIS < 20",
    "reduction_hypnotique": "Réduction hypnotique",
    "bis_recupere": "BIS récupéré",
    # Intubation difficile
    "preox_id": "Pré-oxygénation 100 % O₂",
    "plan_a_echec": "Plan A — Laryngoscopie directe (échec)",
    "plan_b_ml": "Plan B — Masque laryngé 2ᵉ génération",
    "plan_b_insuffisant": "Plan B insuffisant — désaturation",
    "cico_masque_facial": "CICO — masque facial 2 mains",
    "cricothyroidotomie": "Plan D — Cricothyroïdotomie au scalpel",
    "vae_securisee": "Voie aérienne sécurisée",
    # Commun
    "stable_post_induction": "Post-induction stable",
}

# Macro-phase : PRE / PER / POST
MACRO_PHASE = {
    "init": "PRE",
    "stable": "PER",
    "preox": "PRE",
    "post_induction_stable": "PER",
    "stable_post_induction": "PER",
    "entretien_stable": "PER",
    "maintenance_stable": "PER",
    "insufflation_co2": "PER",
    "chirurgie": "PER",
    "chirurgie_stable": "PER",
    "chirurgie_hm_stable": "PER",
    "neurochirurgie_stable": "PER",
    "tentative_intubation": "PER",
    "ventilation_masque": "PER",
    "intubation_reussie": "PER",
    "stable_pre_event": "PER",
    "stable_pre_pneumo": "PER",
    "anaphylaxie_onset": "PER",
    "anaphylaxie_severe": "PER",
    "traitement_adrenaline": "PER",
    "hypotension_progressive": "PER",
    "hypotension_severe": "PER",
    "correction_vasopresseurs": "PER",
    "saignement_modere": "PER",
    "hemorragie_active": "PER",
    "remplissage_transfusion": "PER",
    "bronchospasme_onset": "PER",
    "bronchospasme_severe": "PER",
    "traitement_bronchodilatateur": "PER",
    "bradycardie_progressive": "PER",
    "bradycardie_severe": "PER",
    "traitement_atropine": "PER",
    "stabilisation_bradycardie": "PER",
    "entretien_hta": "PER",
    "stimulus_nociceptif": "PER",
    "crise_hypertensive": "PER",
    "traitement_antihypertenseur": "PER",
    "normalisation_pa": "PER",
    "hm_signes_precoces": "PER",
    "hm_crise": "PER",
    "traitement_dantrolene": "PER",
    "embolie_onset": "PER",
    "embolie_severe": "PER",
    "traitement_embolie": "PER",
    "pneumothorax_onset": "PER",
    "pneumothorax_tension": "PER",
    "exsufflation_drain": "PER",
    "ag_correcte": "PER",
    "allègement_anesthesie": "PER",
    "awareness_active": "PER",
    "approfondissement_ag": "PER",
    "preacr_stable": "PER",
    "preacr_deterioration": "PER",
    "acr_asystolie": "PER",
    "rcp_en_cours": "PER",
    "reveil": "POST",
    "stabilisation": "POST",
    "recuperation": "POST",
    "recuperation_bronchospasme": "POST",
    "recuperation_embolie": "POST",
    "stabilisation_pneumo": "POST",
    "sedation_recuperee": "POST",
    "racs": "POST",
    # Tachycardie
    "entretien_tachy_stable": "PER",
    "stimulus_douloureux": "PER",
    "tachycardie_persistante": "PER",
    "traitement_analgesie": "PER",
    "normalisation_tachy": "PER",
    # Hypothermie
    "chirurgie_debut": "PER",
    "hypothermie_moderee": "PER",
    "hypothermie_severe": "PER",
    "rechauffement_actif": "PER",
    # Burst suppression
    "ag_correcte_bis": "PER",
    "approfondissement_excessif": "PER",
    "burst_suppression_active": "PER",
    "reduction_hypnotique": "PER",
    "bis_recupere": "PER",
    # Intubation difficile
    "preox_id": "PRE",
    "plan_a_echec": "PRE",
    "plan_b_ml": "PRE",
    "plan_b_insuffisant": "PRE",
    "cico_masque_facial": "PRE",
    "cricothyroidotomie": "PER",
    "vae_securisee": "PER",
}

# Patient simulé par scénario (mini CS anesthésie)
SCENARIO_PATIENTS = {
    "normal": {
        "age": 45, "sex": "M", "weight": 75, "height": 178,
        "asa": 1, "ane_type": "AG",
        "opname": "Cholécystectomie cœlioscopique",
        "optype": "Digestif",
        "antecedents": "Aucun",
        "allergies": "Aucune",
        "traitement": "Aucun",
        "jeune": "OK > 6h",
        "mallampati": 1,
        "imc": 23.7,
    },
    "hypotension": {
        "age": 72, "sex": "M", "weight": 82, "height": 172,
        "asa": 2, "ane_type": "AG",
        "opname": "PTH programmée",
        "optype": "Orthopédie",
        "antecedents": "HTA traitée (amlodipine), diabète type 2, BPCO stade I",
        "allergies": "Aucune",
        "traitement": "Amlodipine 5mg, Metformine 1g x2, Spiriva",
        "jeune": "OK > 6h",
        "mallampati": 2,
        "imc": 27.7,
    },
    "desaturation": {
        "age": 55, "sex": "M", "weight": 110, "height": 170,
        "asa": 3, "ane_type": "AG",
        "opname": "Sleeve gastrectomie",
        "optype": "Digestif",
        "antecedents": "Obésité morbide, SAOS appareillé, IOT difficile connue (Cormack 3)",
        "allergies": "Latex",
        "traitement": "PPC nocturne, Omeprazole 20mg",
        "jeune": "OK > 6h",
        "mallampati": 3,
        "imc": 38.1,
    },
    "anaphylaxie": {
        "age": 38, "sex": "F", "weight": 62, "height": 165,
        "asa": 1, "ane_type": "AG",
        "opname": "Appendicectomie cœlioscopique",
        "optype": "Digestif",
        "antecedents": "Terrain atopique, asthme léger",
        "allergies": "Pénicilline (rash cutané)",
        "traitement": "Ventoline SB",
        "jeune": "OK > 6h",
        "mallampati": 1,
        "imc": 22.8,
    },
    "hemorragie": {
        "age": 63, "sex": "F", "weight": 58, "height": 160,
        "asa": 3, "ane_type": "AG",
        "opname": "Hépatectomie droite (CHC)",
        "optype": "Digestif",
        "antecedents": "Cirrhose Child A, CHC segment VII, thrombopénie modérée",
        "allergies": "Aucune",
        "traitement": "Spironolactone 25mg, Furosémide 20mg",
        "jeune": "OK > 6h",
        "mallampati": 2,
        "imc": 22.7,
    },
    "bronchospasme": {
        "age": 32, "sex": "F", "weight": 58, "height": 163,
        "asa": 2, "ane_type": "AG",
        "opname": "Appendicectomie cœlioscopique",
        "optype": "Digestif",
        "antecedents": "Asthme modéré persistant, terrain atopique, eczéma",
        "allergies": "Pénicilline, latex suspecté",
        "traitement": "Sérétide 50/250 x2/j, Ventoline SB",
        "jeune": "OK > 6h",
        "mallampati": 1,
        "imc": 21.8,
    },
    "bradycardie": {
        "age": 75, "sex": "M", "weight": 80, "height": 170,
        "asa": 3, "ane_type": "ALR (rachianesthésie)",
        "opname": "PTG programmée",
        "optype": "Orthopédie",
        "antecedents": "HTA, FA chronique anticoagulée, DFG 52, β-bloquant",
        "allergies": "Aucune",
        "traitement": "Bisoprolol 5mg, Rivaroxaban (arrêté J-3), Lercanidipine 10mg",
        "jeune": "OK > 6h",
        "mallampati": 2,
        "imc": 27.7,
    },
    "crise_hypertensive": {
        "age": 58, "sex": "M", "weight": 90, "height": 175,
        "asa": 2, "ane_type": "AG",
        "opname": "Résection sigmoïdienne cœlioscopique",
        "optype": "Digestif",
        "antecedents": "HTA mal équilibrée, tabac 30 PA, surpoids",
        "allergies": "Aucune",
        "traitement": "Amlodipine 10mg (non pris ce matin), Valsartan 160mg",
        "jeune": "OK > 6h",
        "mallampati": 2,
        "imc": 29.4,
    },
    "hyperthermie_maligne": {
        "age": 25, "sex": "M", "weight": 82, "height": 185,
        "asa": 1, "ane_type": "AG",
        "opname": "Ostéosynthèse fémur",
        "optype": "Orthopédie",
        "antecedents": "Susceptibilité hyperthermie maligne (oncle décédé perop)",
        "allergies": "Succinylcholine — CI absolue",
        "traitement": "Aucun",
        "jeune": "OK > 6h",
        "mallampati": 1,
        "imc": 23.9,
    },
    "embolie_gazeuse": {
        "age": 52, "sex": "F", "weight": 65, "height": 165,
        "asa": 2, "ane_type": "AG",
        "opname": "Craniotomie position assise (méningiome)",
        "optype": "Neurochirurgie",
        "antecedents": "Méningiome parasagittal, migraines",
        "allergies": "Aucune",
        "traitement": "Dexaméthasone 8mg/j, Lévétiracétam 500mg x2",
        "jeune": "OK > 6h",
        "mallampati": 1,
        "imc": 23.9,
    },
    "pneumothorax": {
        "age": 67, "sex": "M", "weight": 72, "height": 172,
        "asa": 3, "ane_type": "AG",
        "opname": "Résection hépatique segment VI",
        "optype": "Digestif",
        "antecedents": "BPCO stade II (VEMS 58%), ex-tabac, emphysème apical",
        "allergies": "Aucune",
        "traitement": "Spiriva, Formotérol, Fluticasone",
        "jeune": "OK > 6h",
        "mallampati": 2,
        "imc": 24.4,
    },
    "reveil_perop": {
        "age": 29, "sex": "F", "weight": 68, "height": 162,
        "asa": 2, "ane_type": "AG (césarienne urgente)",
        "opname": "Césarienne urgente T4 (procidence du cordon)",
        "optype": "Obstétrique",
        "antecedents": "G1P0, 38SA, pré-éclampsie modérée",
        "allergies": "Aucune",
        "traitement": "Nicardipine IVSE, MgSO4 IVSE",
        "jeune": "Non à jeun (repas il y a 3h)",
        "mallampati": 3,
        "imc": 25.9,
    },
    "acr": {
        "age": 72, "sex": "M", "weight": 85, "height": 170,
        "asa": 4, "ane_type": "AG",
        "opname": "Pontage aorto-coronarien",
        "optype": "Cardiaque",
        "antecedents": "Coronaropathie tritronculaire, FE 30%, ATCD IDM x2, DT2, IRC",
        "allergies": "Aucune",
        "traitement": "Aspirine, Bisoprolol, Furosémide, Spironolactone, Insuline",
        "jeune": "OK > 6h",
        "mallampati": 2,
        "imc": 29.4,
    },
    "tachycardie": {
        "age": 48, "sex": "M", "weight": 84, "height": 178,
        "asa": 2, "ane_type": "AG",
        "opname": "Résection colique droite cœlioscopique",
        "optype": "Digestif",
        "antecedents": "HTA légère, tabac 10 PA, douleurs chroniques lombaires",
        "allergies": "Aucune",
        "traitement": "Ramipril 5mg",
        "jeune": "OK > 6h",
        "mallampati": 2,
        "imc": 26.5,
    },
    "hypothermie": {
        "age": 70, "sex": "F", "weight": 60, "height": 160,
        "asa": 3, "ane_type": "AG",
        "opname": "Résection antérieure du rectum (chirurgie longue 4h)",
        "optype": "Digestif",
        "antecedents": "BPCO stade I, HTA, anémie ferriprive préopératoire",
        "allergies": "Aucune",
        "traitement": "Amlodipine 5mg, Fer 80mg",
        "jeune": "OK > 8h",
        "mallampati": 2,
        "imc": 23.4,
    },
    "burst_suppression": {
        "age": 82, "sex": "F", "weight": 52, "height": 155,
        "asa": 3, "ane_type": "AG (TIVA propofol)",
        "opname": "Cœlioscopie gynécologique (kyste ovarien)",
        "optype": "Gynécologie",
        "antecedents": "ATCD AVC ischémique, FA, insuffisance rénale légère, fragilité",
        "allergies": "Aucune",
        "traitement": "Apixaban (arrêté J-5), Lercanidipine, Escitalopram",
        "jeune": "OK > 6h",
        "mallampati": 2,
        "imc": 21.6,
    },
    "intubation_difficile": {
        "age": 42, "sex": "F", "weight": 100, "height": 162,
        "asa": 3, "ane_type": "AG (intubation difficile prévue)",
        "opname": "Cholécystite aiguë laparo-convertie",
        "optype": "Digestif",
        "antecedents": "Obésité morbide, SAOS non appareillé, RGO, Cormack 3 ATCD",
        "allergies": "Latex",
        "traitement": "Oméprazole 40mg, Metformine 1g (arrêtée)",
        "jeune": "Non à jeun (repas il y a 5h), estomac plein",
        "mallampati": 4,
        "imc": 38.1,
    },
}


def _fmt_elapsed(seconds: int) -> str:
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}h{m:02d}" if h else f"{m}min{s:02d}"


@dataclass
class SimulatedRoom:
    room_id: str
    scenario_name: str
    state: PhysioState = field(default_factory=PhysioState)
    scenario: Scenario = field(default_factory=NormalScenario)
    phase: str = "init"

    def __post_init__(self):
        scenario_cls = SCENARIOS.get(self.scenario_name, NormalScenario)
        self.scenario = scenario_cls()

    def tick(self) -> dict:
        """Avance d'un pas (5 secondes) et retourne le message MQTT."""
        self.phase = self.scenario.apply(self.state)
        self.state.add_noise()
        self.state.compute_pam()

        elapsed_s = self.scenario.step * 5
        macro = MACRO_PHASE.get(self.phase, "PER")
        patient = SCENARIO_PATIENTS.get(self.scenario.name, {})

        return {
            "room_id": self.room_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenario": self.scenario.name,
            "phase": self.phase,
            "phase_label": PHASE_LABELS.get(self.phase, self.phase),
            "macro_phase": macro,
            "elapsed_s": elapsed_s,
            "elapsed_fmt": _fmt_elapsed(elapsed_s),
            "patient_info": patient,
            "vitals": {
                "hr": round(float(self.state.hr), 1),
                "spo2": round(float(self.state.spo2), 1),
                "pas": round(float(self.state.pas), 0),
                "pad": round(float(self.state.pad), 0),
                "pam": round(float(self.state.pam), 0),
                "etco2": round(float(self.state.etco2), 1),
                "fr": round(float(self.state.fr), 0),
                "temp": round(float(self.state.temp), 1),
            },
            "ventilator": {
                "mode": self.state.vent_mode,
                "vt": round(float(self.state.vt)),
                "vt_kg": round(float(self.state.vt / 75), 1),  # 75 kg patient
                "mv": round(float(self.state.fr * self.state.vt / 1000), 1),
                "ppeak": round(float(self.state.ppeak), 1),
                "pplat": round(float(self.state.pplat), 1),
                "peep": round(float(self.state.peep), 1),
                "fio2": round(float(self.state.fio2)),
                "ratio_ie": "1:2",
            },
            "bis": {
                "bis": round(float(self.state.bis)),
                "sqi": round(float(self.state.sqi)),
                "emg": round(float(self.state.emg), 1),
                "sr": round(float(self.state.sr), 1),
            },
            "aivoc_hypnotic": {
                "drug": "propofol",
                "model": "Schnider",
                "target_type": "effect_site",
                "target": round(float(self.state.propofol_target), 1),
                "predicted_plasma": round(float(self.state.propofol_plasma), 2),
                "predicted_effect": round(float(self.state.propofol_effect), 2),
                "infusion_rate": round(float(self.state.propofol_rate), 1),
            },
            "aivoc_opioid": {
                "drug": "remifentanil",
                "model": "Minto",
                "target_type": "effect_site",
                "target": round(float(self.state.remi_target), 1),
                "predicted_plasma": round(float(self.state.remi_plasma), 2),
                "predicted_effect": round(float(self.state.remi_effect), 2),
                "infusion_rate": round(float(self.state.remi_rate), 1),
            },
        }


# ══════════════════════════════════════════════════════════════
#  MAIN — avec contrôle MQTT depuis le backend
# ══════════════════════════════════════════════════════════════
