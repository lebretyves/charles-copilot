# Hypotension Model Evaluation

- Generated at: `2026-04-01T23:32:59.017300+00:00`
- Cases with waveforms: `[1, 3]`
- Cases without waveforms: `[52, 53]`

## Summary
- Case `1` / `waveforms_enabled`: onset `1826.0 s`, early `356.0 s`, confirmed `678.0 s`, peak `refractory_hypotension`
- Case `3` / `waveforms_enabled`: onset `388.0 s`, early `320.0 s`, confirmed `446.0 s`, peak `probable_hypotension`
- Case `52` / `numeric_only`: onset `408.0 s`, early `376.0 s`, confirmed `376.0 s`, peak `critical_hypotension`
- Case `53` / `numeric_only`: onset `668.0 s`, early `686.0 s`, confirmed `710.0 s`, peak `critical_hypotension`

## Detailed Results

### Case 1 (waveforms_enabled)
- Reference onset: `1826.0 s`
- First early transition: `356.0 s`
- First probable: `678.0 s`
- First confirmed: `678.0 s`
- First critical: `678.0 s`
- Early anticipation vs onset: `1470.0 s`
- Confirmed anticipation vs onset: `1148.0 s`
- Peak state: `refractory_hypotension` at `4620.0 s`
- Peak risk / severity / confidence: `0.438625` / `0.703` / `0.858349`
- Baseline MAP / SAP / EtCO2: `100.0` / `177.0` / `None`
- Peak cause profile: `{"vasoplegic": 0.155046, "hypovolemic": 0.063439, "cardiodepressive": 0.166604, "brady_dependent": 0.079497, "obstructive": 0.033828, "artifact": 0.149947, "indeterminate": 0.029989, "mixed": 0.32165}`
- Peak explanation: `MAP delta_vs_baseline=23.4%; MAP=53.0; SAP=78.0; multicurve_score=0.50; low_BIS_context; contradiction_score=0.50; dominant_cause=mixed:0.32; confidence=0.86`

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

### Case 52 (numeric_only)
- Reference onset: `408.0 s`
- First early transition: `376.0 s`
- First probable: `376.0 s`
- First confirmed: `376.0 s`
- First critical: `376.0 s`
- Early anticipation vs onset: `32.0 s`
- Confirmed anticipation vs onset: `32.0 s`
- Peak state: `critical_hypotension` at `490.0 s`
- Peak risk / severity / confidence: `0.41` / `0.71` / `0.66`
- Baseline MAP / SAP / EtCO2: `90.0` / `134.0` / `32.0`
- Peak cause profile: `{"vasoplegic": 0.343474, "hypovolemic": 0.060844, "cardiodepressive": 0.161923, "brady_dependent": 0.147203, "obstructive": 0.041217, "artifact": 0.196271, "indeterminate": 0.049068, "mixed": 0.0}`
- Peak explanation: `MAP delta_vs_baseline=33.8%; MAP=55.0; SAP=75.0; induction_related_phase; contradiction_score=0.40; dominant_cause=vasoplegic:0.34; confidence=0.66`

### Case 53 (numeric_only)
- Reference onset: `668.0 s`
- First early transition: `686.0 s`
- First probable: `710.0 s`
- First confirmed: `710.0 s`
- First critical: `710.0 s`
- Early anticipation vs onset: `-18.0 s`
- Confirmed anticipation vs onset: `-42.0 s`
- Peak state: `critical_hypotension` at `712.0 s`
- Peak risk / severity / confidence: `0.635457` / `0.666424` / `0.715833`
- Baseline MAP / SAP / EtCO2: `None` / `None` / `None`
- Peak cause profile: `{"vasoplegic": 0.186643, "hypovolemic": 0.056775, "cardiodepressive": 0.169669, "brady_dependent": 0.113527, "obstructive": 0.085145, "artifact": 0.010643, "indeterminate": 0.021286, "mixed": 0.356312}`
- Peak explanation: `MAP delta_vs_baseline=34.1%; MAP=48.0; SAP=69.0; EtCO2_drop_score=1.00; low_BIS_context; induction_related_phase; contradiction_score=0.05; dominant_cause=mixed:0.36; confidence=0.72`
