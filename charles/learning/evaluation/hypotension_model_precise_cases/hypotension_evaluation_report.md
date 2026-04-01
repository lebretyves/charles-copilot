# Hypotension Model Evaluation

- Generated at: `2026-04-01T23:45:15.697494+00:00`
- Cases with waveforms: `[3, 46]`
- Cases without waveforms: `[52, 97]`

## Summary
- Case `3` / `waveforms_enabled`: onset `388.0 s`, early `320.0 s`, confirmed `446.0 s`, peak `probable_hypotension`
- Case `46` / `waveforms_enabled`: onset `644.0 s`, early `568.0 s`, confirmed `702.0 s`, peak `critical_hypotension`
- Case `52` / `numeric_only`: onset `408.0 s`, early `376.0 s`, confirmed `376.0 s`, peak `critical_hypotension`
- Case `97` / `numeric_only`: onset `1542.0 s`, early `1528.0 s`, confirmed `1528.0 s`, peak `critical_hypotension`

## Detailed Results

### Case 3 (waveforms_enabled)
- Reference onset: `388.0 s`
- First early transition: `320.0 s`
- First probable: `346.0 s`
- First confirmed: `446.0 s`
- First critical: `None s`
- Early anticipation vs onset: `68.0 s`
- Confirmed anticipation vs onset: `-58.0 s`
- Peak state: `probable_hypotension` at `4126.0 s`
- Peak risk / severity / confidence: `0.709698` / `0.285` / `0.658465`
- Baseline MAP / SAP / EtCO2: `100.0` / `130.0` / `None`
- Peak cause profile: `{"vasoplegic": 0.082357, "hypovolemic": 0.128908, "cardiodepressive": 0.191775, "brady_dependent": 0.021177, "obstructive": 0.164714, "artifact": 0.018193, "indeterminate": 0.036386, "mixed": 0.356489}`
- Peak explanation: `SAP=31.0; EtCO2_drop_score=1.00; pleth_drop_score=1.00; multicurve_score=0.75; low_BIS_context; dominant_cause=mixed:0.36; confidence=0.66`

### Case 46 (waveforms_enabled)
- Reference onset: `644.0 s`
- First early transition: `568.0 s`
- First probable: `656.0 s`
- First confirmed: `702.0 s`
- First critical: `724.0 s`
- Early anticipation vs onset: `76.0 s`
- Confirmed anticipation vs onset: `-58.0 s`
- Peak state: `critical_hypotension` at `750.0 s`
- Peak risk / severity / confidence: `0.624237` / `0.624237` / `0.977358`
- Baseline MAP / SAP / EtCO2: `91.0` / `119.0` / `None`
- Peak cause profile: `{"vasoplegic": 0.321652, "hypovolemic": 0.133709, "cardiodepressive": 0.219364, "brady_dependent": 0.118229, "obstructive": 0.059203, "artifact": 0.088706, "indeterminate": 0.059137, "mixed": 0.0}`
- Peak explanation: `MAP delta_vs_baseline=25.0%; MAP=55.0; SAP=85.0; pleth_drop_score=0.54; multicurve_score=0.47; induction_related_phase; contradiction_score=0.15; dominant_cause=vasoplegic:0.32; confidence=0.98`

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
- Peak explanation: `MAP delta_vs_baseline=33.8%; MAP=55.0; SAP=75.0; induction_related_phase; contradiction_score=0.40; dominant_cause=vasoplegic:0.34; confidence=0.66`

### Case 97 (numeric_only)
- Reference onset: `1542.0 s`
- First early transition: `1528.0 s`
- First probable: `1528.0 s`
- First confirmed: `1528.0 s`
- First critical: `2716.0 s`
- Early anticipation vs onset: `14.0 s`
- Confirmed anticipation vs onset: `14.0 s`
- Peak state: `critical_hypotension` at `6376.0 s`
- Peak risk / severity / confidence: `0.592` / `0.592` / `0.643333`
- Baseline MAP / SAP / EtCO2: `83.0` / `112.0` / `None`
- Peak cause profile: `{"vasoplegic": 0.135305, "hypovolemic": 0.016207, "cardiodepressive": 0.174618, "brady_dependent": 0.159182, "obstructive": 0.0, "artifact": 0.144711, "indeterminate": 0.036178, "mixed": 0.3338}`
- Peak explanation: `MAP delta_vs_baseline=49.0%; MAP=41.0; SAP=41.0; low_BIS_context; contradiction_score=0.40; dominant_cause=mixed:0.33; confidence=0.64`
