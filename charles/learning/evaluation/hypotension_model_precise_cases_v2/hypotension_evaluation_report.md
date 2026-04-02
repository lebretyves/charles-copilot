# Hypotension Model Evaluation

- Generated at: `2026-04-02T04:52:23.095321+00:00`
- Cases with waveforms: `[3, 46]`
- Cases without waveforms: `[52, 97]`

## Summary
- Case `3` / `waveforms_enabled`: onset `388.0 s`, early `320.0 s`, confirmed `446.0 s`, peak `probable_hypotension`
- Case `46` / `waveforms_enabled`: onset `644.0 s`, early `446.0 s`, confirmed `702.0 s`, peak `critical_hypotension`
- Case `52` / `numeric_only`: onset `408.0 s`, early `376.0 s`, confirmed `376.0 s`, peak `critical_hypotension`
- Case `97` / `numeric_only`: onset `1542.0 s`, early `1158.0 s`, confirmed `1528.0 s`, peak `critical_hypotension`

## Detailed Results

### Case 3 (waveforms_enabled)
- Reference onset: `388.0 s`
- First early transition: `320.0 s`
- First probable: `320.0 s`
- First confirmed: `446.0 s`
- First critical: `None s`
- Early anticipation vs onset: `68.0 s`
- Confirmed anticipation vs onset: `-58.0 s`
- Peak state: `probable_hypotension` at `4126.0 s`
- Peak risk / severity / confidence: `0.703285` / `0.285` / `0.658465`
- Baseline MAP / SAP / EtCO2: `100.0` / `130.0` / `None`
- Peak cause profile: `{"vasoplegic": 0.081667, "hypovolemic": 0.127828, "cardiodepressive": 0.190168, "brady_dependent": 0.021, "obstructive": 0.163334, "artifact": 0.020834, "indeterminate": 0.041668, "mixed": 0.353502}`
- Peak explanation: `SAP=31.0; EtCO2_drop_score=1.00; pleth_drop_score=1.00; multicurve_score=0.75; transition_coherence=1.00; low_BIS_context; dominant_cause=mixed:0.35; confidence=0.66`

### Case 46 (waveforms_enabled)
- Reference onset: `644.0 s`
- First early transition: `446.0 s`
- First probable: `644.0 s`
- First confirmed: `702.0 s`
- First critical: `724.0 s`
- Early anticipation vs onset: `198.0 s`
- Confirmed anticipation vs onset: `-58.0 s`
- Peak state: `critical_hypotension` at `750.0 s`
- Peak risk / severity / confidence: `0.817456` / `0.6785` / `0.998253`
- Baseline MAP / SAP / EtCO2: `91.0` / `119.0` / `None`
- Peak cause profile: `{"vasoplegic": 0.185859, "hypovolemic": 0.1203, "cardiodepressive": 0.154756, "brady_dependent": 0.072826, "obstructive": 0.049783, "artifact": 0.045517, "indeterminate": 0.030344, "mixed": 0.340615}`
- Peak explanation: `MAP delta_vs_baseline=34.7%; MAP=55.0; SAP=85.0; pleth_drop_score=1.00; multicurve_score=0.67; incipient_burden_score=1.00; transition_coherence=1.00; induction_related_phase; contradiction_score=0.15; dominant_cause=mixed:0.34; confidence=1.00`

### Case 52 (numeric_only)
- Reference onset: `408.0 s`
- First early transition: `376.0 s`
- First probable: `376.0 s`
- First confirmed: `376.0 s`
- First critical: `376.0 s`
- Early anticipation vs onset: `32.0 s`
- Confirmed anticipation vs onset: `32.0 s`
- Peak state: `critical_hypotension` at `490.0 s`
- Peak risk / severity / confidence: `0.71` / `0.71` / `0.66`
- Baseline MAP / SAP / EtCO2: `90.0` / `134.0` / `32.0`
- Peak cause profile: `{"vasoplegic": 0.343474, "hypovolemic": 0.060844, "cardiodepressive": 0.161923, "brady_dependent": 0.147203, "obstructive": 0.041217, "artifact": 0.196271, "indeterminate": 0.049068, "mixed": 0.0}`
- Peak explanation: `MAP delta_vs_baseline=38.9%; MAP=55.0; SAP=75.0; incipient_burden_score=1.00; transition_coherence=0.75; induction_related_phase; contradiction_score=0.40; dominant_cause=vasoplegic:0.34; confidence=0.66`

### Case 97 (numeric_only)
- Reference onset: `1542.0 s`
- First early transition: `1158.0 s`
- First probable: `1528.0 s`
- First confirmed: `1528.0 s`
- First critical: `2716.0 s`
- Early anticipation vs onset: `384.0 s`
- Confirmed anticipation vs onset: `14.0 s`
- Peak state: `critical_hypotension` at `6376.0 s`
- Peak risk / severity / confidence: `0.592` / `0.592` / `0.643333`
- Baseline MAP / SAP / EtCO2: `83.0` / `112.0` / `None`
- Peak cause profile: `{"vasoplegic": 0.135305, "hypovolemic": 0.016207, "cardiodepressive": 0.174618, "brady_dependent": 0.159182, "obstructive": 0.0, "artifact": 0.144711, "indeterminate": 0.036178, "mixed": 0.3338}`
- Peak explanation: `MAP delta_vs_baseline=55.3%; MAP=41.0; SAP=41.0; incipient_burden_score=1.00; transition_coherence=0.75; low_BIS_context; contradiction_score=0.40; dominant_cause=mixed:0.33; confidence=0.64`
