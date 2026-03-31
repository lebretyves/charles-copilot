from __future__ import annotations

import numpy as np

WAVE_CHUNK_S = 0.25
N_500 = int(500 * WAVE_CHUNK_S)
N_25 = int(25 * WAVE_CHUNK_S)
N_128 = int(128 * WAVE_CHUNK_S)


def _ecg_pqrst(phase: np.ndarray) -> np.ndarray:
    p = 0.15 * np.exp(-((phase - 0.12) / 0.040) ** 2)
    q = -0.08 * np.exp(-((phase - 0.28) / 0.012) ** 2)
    r = 1.20 * np.exp(-((phase - 0.33) / 0.016) ** 2)
    s = -0.18 * np.exp(-((phase - 0.40) / 0.012) ** 2)
    t = 0.28 * np.exp(-((phase - 0.65) / 0.080) ** 2)
    return p + q + r + s + t


def generate_synth_waves(state, room_id: str, t_start: float, rng: np.random.Generator | None = None) -> dict:
    hr = max(30.0, float(state.hr))
    spo2 = float(state.spo2)
    pas = float(state.pas)
    pad = float(state.pad)
    etco2 = float(state.etco2)
    fr = max(4.0, float(state.fr))
    ppeak = float(state.ppeak)
    pplat = float(state.pplat)
    peep = float(state.peep)
    bis = float(state.bis)

    rng = rng or np.random.default_rng()

    t500 = np.linspace(t_start, t_start + WAVE_CHUNK_S, N_500, endpoint=False)
    period_c = 60.0 / hr
    ph_c = (t500 % period_c) / period_c
    ecg_raw = _ecg_pqrst(ph_c) + rng.normal(0, 0.02, N_500)
    chunk_ecg = [round(float(value), 4) for value in ecg_raw]

    p_main = 0.80 * np.exp(-((ph_c - 0.25) / 0.12) ** 2)
    p_dicrotic = 0.12 * np.exp(-((ph_c - 0.55) / 0.05) ** 2)
    p_base = 0.05 * (spo2 / 100.0)
    pleth_raw = p_main + p_dicrotic + p_base + rng.normal(0, 0.01, N_500)
    chunk_pleth = [round(float(value), 4) for value in np.clip(pleth_raw, 0.0, 1.2)]

    pulse_h = pas - pad
    a_sys = pulse_h * np.exp(-((ph_c - 0.20) / 0.12) ** 2)
    a_dic = pulse_h * 0.2 * np.exp(-((ph_c - 0.50) / 0.05) ** 2)
    art_raw = pad + a_sys + a_dic + rng.normal(0, 0.8, N_500)
    chunk_art = [round(float(value), 2) for value in np.clip(art_raw, pad - 5, pas + 10)]

    t25 = np.linspace(t_start, t_start + WAVE_CHUNK_S, N_25, endpoint=False)
    period_r = 60.0 / fr
    ph_r = (t25 % period_r) / period_r
    co2_raw = np.where(
        ph_r < 0.36,
        0.0,
        np.where(
            ph_r < 0.48,
            etco2 * (ph_r - 0.36) / 0.12,
            np.where(
                ph_r < 0.72,
                etco2,
                np.where(ph_r < 0.80, etco2 * (0.80 - ph_r) / 0.08, 0.0),
            ),
        ),
    ) + rng.normal(0, 0.3, N_25)
    chunk_co2 = [round(float(value), 3) for value in np.clip(co2_raw, 0.0, 80.0)]

    awp_raw = np.where(
        ph_r < 0.05,
        peep + (ppeak - peep) * (ph_r / 0.05),
        np.where(
            ph_r < 0.15,
            ppeak,
            np.where(
                ph_r < 0.40,
                pplat + (ppeak - pplat) * np.exp(-(ph_r - 0.15) / 0.05),
                peep + (pplat - peep) * np.exp(-(ph_r - 0.40) / 0.15),
            ),
        ),
    ) + rng.normal(0, 0.3, N_25)
    chunk_awp = [round(float(value), 3) for value in np.clip(awp_raw, peep - 2, ppeak + 5)]

    amp_eeg = 80.0 * (1.0 - bis / 100.0) + 10.0
    raw_eeg = rng.normal(0, amp_eeg, N_128)
    alpha = 0.65
    for index in range(1, N_128):
        raw_eeg[index] = alpha * raw_eeg[index - 1] + (1.0 - alpha) * raw_eeg[index]
    chunk_eeg = [round(float(value), 4) for value in raw_eeg]

    return {
        "type": "wave_chunk",
        "room_id": room_id,
        "t": round(t_start, 3),
        "ecg": chunk_ecg,
        "pleth": chunk_pleth,
        "art": chunk_art,
        "co2": chunk_co2,
        "awp": chunk_awp,
        "eeg": chunk_eeg,
    }
