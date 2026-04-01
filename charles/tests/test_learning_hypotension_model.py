from __future__ import annotations

from learning.problems.hypotension_model import (
    HypotensionBaselines,
    HypotensionDetector,
    HypotensionSnapshot,
)


def _baselines() -> HypotensionBaselines:
    return HypotensionBaselines(
        patient_t0={
            "map": 85.0,
            "sap": 125.0,
            "hr": 72.0,
            "etco2": 35.0,
            "spo2": 99.0,
            "bis": 48.0,
            "art_wave_amplitude": 38.0,
            "pleth_wave_amplitude": 1.0,
            "capno_wave_amplitude": 28.0,
        },
        stable={
            "map": 82.0,
            "sap": 120.0,
            "hr": 70.0,
            "etco2": 34.0,
            "spo2": 99.0,
            "bis": 47.0,
            "art_wave_amplitude": 36.0,
            "pleth_wave_amplitude": 0.95,
            "capno_wave_amplitude": 27.0,
        },
        reliability=0.95,
    )


def test_detector_confirms_sustained_hypotension():
    detector = HypotensionDetector(_baselines())
    outputs = []
    for time_s, map_value, sap_value, etco2, pleth_amp in [
        (0, 82, 120, 34, 0.95),
        (10, 80, 118, 34, 0.94),
        (20, 76, 110, 33, 0.88),
        (30, 72, 102, 32, 0.82),
        (40, 67, 96, 31, 0.76),
        (50, 63, 88, 30, 0.68),
        (60, 61, 86, 29, 0.62),
        (70, 60, 85, 29, 0.60),
        (80, 62, 87, 30, 0.61),
        (90, 64, 89, 30, 0.62),
        (100, 62, 87, 30, 0.62),
    ]:
        outputs.append(
            detector.update(
                HypotensionSnapshot(
                    time_s=float(time_s),
                    map_value=float(map_value),
                    sap_value=float(sap_value),
                    hr=92.0,
                    etco2=float(etco2),
                    spo2=98.0,
                    bis=40.0,
                    art_wave_amplitude=25.0,
                    art_wave_slope=180.0,
                    pleth_wave_amplitude=float(pleth_amp),
                    pleth_wave_slope=45.0,
                    capno_wave_amplitude=21.0,
                    capno_wave_slope=18.0,
                )
            )
        )

    states = [output.state for output in outputs]
    assert "early_transition" in states or "probable_hypotension" in states
    assert "confirmed_hypotension" in states
    first_early = next(output.time_s for output in outputs if output.state in {"early_transition", "probable_hypotension", "confirmed_hypotension", "critical_hypotension", "refractory_hypotension"})
    first_confirmed = next(output.time_s for output in outputs if output.state in {"confirmed_hypotension", "critical_hypotension", "refractory_hypotension"})
    assert first_early <= 30.0
    assert first_confirmed >= 50.0
    assert outputs[-1].risk_5min >= 0.70


def test_detector_downweights_pressure_artifact():
    detector = HypotensionDetector(_baselines())
    stable = detector.update(
        HypotensionSnapshot(
            time_s=0.0,
            map_value=83.0,
            sap_value=121.0,
            hr=74.0,
            etco2=34.0,
            spo2=99.0,
            bis=47.0,
            art_wave_amplitude=36.0,
            art_wave_slope=200.0,
            pleth_wave_amplitude=0.95,
            pleth_wave_slope=50.0,
            capno_wave_amplitude=27.0,
            capno_wave_slope=20.0,
        )
    )
    artifact = detector.update(
        HypotensionSnapshot(
            time_s=10.0,
            map_value=32.0,
            sap_value=55.0,
            hr=76.0,
            etco2=34.0,
            spo2=99.0,
            bis=46.0,
            art_wave_amplitude=35.5,
            art_wave_slope=198.0,
            pleth_wave_amplitude=0.96,
            pleth_wave_slope=48.0,
            capno_wave_amplitude=27.1,
            capno_wave_slope=20.0,
        )
    )

    assert stable.state == "stable"
    assert artifact.state in {"stable", "early_transition"}
    assert artifact.confidence < 0.85
    assert artifact.cause_profile["artifact"] >= 0.15
    assert artifact.contradiction_score >= 0.30


def test_waveforms_help_earlier_transition_than_numeric_only():
    with_wave = HypotensionDetector(_baselines())
    without_wave = HypotensionDetector(_baselines())
    with_wave_time = None
    without_wave_time = None
    sequence = [
        (0, 82, 120, 34, 0.95, 36.0, 27.0),
        (10, 80, 118, 34, 0.93, 34.0, 26.5),
        (20, 77, 112, 33, 0.86, 31.0, 24.0),
        (30, 74, 108, 33, 0.80, 28.0, 22.0),
        (40, 70, 101, 32, 0.72, 24.0, 20.0),
        (50, 67, 98, 31, 0.66, 21.0, 18.0),
        (60, 64, 90, 30, 0.62, 19.0, 17.0),
    ]
    for time_s, map_value, sap_value, etco2, pleth_amp, art_amp, capno_amp in sequence:
        out_with = with_wave.update(
            HypotensionSnapshot(
                time_s=float(time_s),
                map_value=float(map_value),
                sap_value=float(sap_value),
                hr=88.0,
                etco2=float(etco2),
                spo2=98.0,
                bis=43.0,
                art_wave_amplitude=float(art_amp),
                art_wave_slope=180.0,
                pleth_wave_amplitude=float(pleth_amp),
                pleth_wave_slope=40.0,
                capno_wave_amplitude=float(capno_amp),
                capno_wave_slope=18.0,
            )
        )
        out_without = without_wave.update(
            HypotensionSnapshot(
                time_s=float(time_s),
                map_value=float(map_value),
                sap_value=float(sap_value),
                hr=88.0,
                etco2=float(etco2),
                spo2=98.0,
                bis=43.0,
            )
        )
        if with_wave_time is None and out_with.state in {"early_transition", "probable_hypotension", "confirmed_hypotension", "critical_hypotension", "refractory_hypotension"}:
            with_wave_time = out_with.time_s
        if without_wave_time is None and out_without.state in {"early_transition", "probable_hypotension", "confirmed_hypotension", "critical_hypotension", "refractory_hypotension"}:
            without_wave_time = out_without.time_s

    assert with_wave_time is not None
    assert without_wave_time is not None
    assert with_wave_time <= without_wave_time
