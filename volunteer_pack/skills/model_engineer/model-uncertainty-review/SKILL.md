---
name: model-uncertainty-review
description: Review model comparison, calibration, drift, and explanation while keeping unsupported inference visible.
---

# Model Uncertainty Review

## Use When

- a score or model supports a decision;
- a candidate model is compared with a baseline;
- drift, calibration, or explanation quality is in question.

## Inputs

- label and sample contracts;
- baseline and candidate outputs;
- validation slices, uncertainty estimates, and operating constraints.

## Procedure

1. Verify label, sample, split, leakage, and comparison parity.
2. Review discrimination, calibration, stability, and subgroup behavior.
3. Separate predictive evidence from causal interpretation.
4. Test sensitivity to window, threshold, and missingness.
5. Define failure conditions and the next validation step.

## Output

Comparative evidence, uncertainty boundary, unsupported claims, and follow-up
tests.

## Stop Conditions

Do not promote a model from offline improvement alone or when comparison
contracts differ materially.
