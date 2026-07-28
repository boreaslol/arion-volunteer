---
name: data-quality-gate
description: Check whether a bounded dataset is trustworthy enough for analysis before conclusions or model work begin.
---

# Data Quality Gate

## Use When

- a dataset enters a new analysis;
- a comparison changes grain, window, source, or population;
- missingness or duplication could change the conclusion.

## Inputs

- dataset or reviewed query result;
- expected grain, keys, window, and population;
- required fields and acceptance thresholds.

## Procedure

1. Verify schema, types, grain, and key uniqueness.
2. Measure row coverage, missingness, duplicates, and impossible values.
3. Check time and population boundaries.
4. Compare source totals with an independent control when available.
5. Classify the dataset as ready, conditionally usable, or blocked.

## Output

A gate result, measurements, exclusions, and residual data risk.

## Stop Conditions

Stop when the required grain or source cannot be established, or when repairs
would require inventing data.
