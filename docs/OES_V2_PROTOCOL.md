# OES V2: Physics-Constrained Compact Representation

## Why a second OES design is justified

The first OES pilot was a valid negative result. It appended 25,536 raw
phase-statistics to 310 process features and asked one model to predict both
the wafer-global shift and the 89-point spatial residual. With only 29-30
training wafers per outer fold, it worsened lot-macro MAE by 1.68%.

V2 changes the scientific hypothesis, rather than simply tuning the failed
model:

```text
Chamber-level OES  -> wafer-global stepheight mean shift
Process data       -> wafer-map spatial residual
```

This is a testable ownership constraint, not an assertion that OES can never
contain spatial information. The comparison will show whether the constraint
improves unseen-lot behavior.

## Fixed V2 design

1. Every OES row is divided by its broadband intensity before averaging. This
   makes the representation emphasize spectral shape rather than total optical
   gain.
2. Six time-aware spectral summaries are formed for each wafer: active, early,
   late, long Bosch phase, short Bosch phase, and cycle-to-cycle slope.
3. Only the outer-training wafers fit the SVD/PCA basis. Candidate dimensions
   are 2, 4, and 8; the inner leave-one-lot-out split selects the dimension and
   Ridge penalty.
4. Compact OES scores predict the scalar mean shift only. The frozen
   process-only PLS model predicts the spatial residual.
5. The final map is `training-map template + OES mean shift + process residual`.

## Evaluation and stop rule

The preselected Lots 2, 4, 6, and 9 remain the only pilot lots. The primary
metric is lot-macro full-map MAE. V2 proceeds to a broader download only when
it achieves both:

- at least 5% lower MAE than process-only PLS; and
- improvement in at least three of four held-out lots.

The same threshold used for V1 is retained. It is not relaxed after observing
V1's failure.

## Required Visual Evidence

Every V2 result dashboard must include one representative held-out wafer with
the following maps on matched color scales:

1. measured 89-point stepheight;
2. process-only prediction;
3. physics-constrained prediction;
4. process-only error; and
5. physics-constrained error.

The representative wafer must be selected by a written deterministic rule,
such as the median improvement among OES-improved held-out wafers. It cannot be
manually selected for appearance.

## Fixed Decisions

The recommended defaults are already fixed in
`configs/analysis/oes_v2_physics_constrained.json` and must be retained when
the V2 result is interpreted:

| Decision | Recommended default | Why it matters |
|---|---|---|
| OES ownership | Mean shift only | Prevents a global sensor from freely fitting a spatial map with 29 training wafers. |
| Success gate | >=5% and >=3/4 lots | Preserves the V1 standard and blocks post-hoc threshold relaxation. |
| Scope after a failure | Stop OES expansion | Avoids spending storage and compute to rescue a failed design. |
| Visualization | Include matched-scale wafer maps | Makes spatial claims inspectable rather than hiding them in MAE alone. |

## Evidence Boundary

V2 can establish only whether this representation improves the four-lot pilot.
It cannot establish a production OES deployment, causal plasma chemistry, or
factory-wide transfer. A pass would justify, not replace, the broader ten-lot
evaluation.
