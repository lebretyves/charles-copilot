# Hypotension V2 vs V1

Comparaison sur les 4 cas de reference:

- `case 3` waveforms:
  - `early_transition`: `320 s -> 320 s` (`0 s`)
  - `probable`: `346 s -> 320 s` (`+26 s`)
  - `confirmed`: `446 s -> 446 s` (`0 s`)
- `case 46` waveforms:
  - `early_transition`: `568 s -> 446 s` (`+122 s`)
  - `probable`: `656 s -> 644 s` (`+12 s`)
  - `confirmed`: `702 s -> 702 s` (`0 s`)
- `case 52` numeric only:
  - `early_transition`: `376 s -> 376 s` (`0 s`)
  - `probable`: `376 s -> 376 s` (`0 s`)
  - `confirmed`: `376 s -> 376 s` (`0 s`)
- `case 97` numeric only:
  - `early_transition`: `1528 s -> 1158 s` (`+370 s`)
  - `probable`: `1528 s -> 1528 s` (`0 s`)
  - `confirmed`: `1528 s -> 1528 s` (`0 s`)

Lecture:

- le gain principal de `v2` est sur la partie `early/probable` avec waveforms
- `confirmed` reste strictement inchangé sur les 4 cas
- `case 97` montre que `early_transition` devient tres precoce lorsqu'un patient reste longtemps en zone borderline autour de `MAP 65`
- en pratique, cet effet doit etre interprete comme un pre-signal faible et non comme une hypotension confirmee
