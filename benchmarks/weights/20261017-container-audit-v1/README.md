# Unchanged container audit

The observer reproduces the exact published weight container and attributes all
3,716,667 bytes: tensor bodies plus their metadata consume 3,716,650 bytes and
the header/final range-coder flush consume 17. It observes the existing writer;
it does not change its compression model.

Int4 tensors account for 3,629,108 bytes (97.6%). The MLP up and down matrices
alone account for 1,101,711 and 1,090,566 bytes. The fitted independent-symbol
entropy summed over int4 tensors is 3,626,890.87 bytes, only 2,217.13 below the
measured coding cost. Fitting each row separately gives 3,574,211.41 bytes,
54,896.59 below that measured cost **before paying for the row distributions**.
These are diagnostics, not achievable sizes or lower bounds for arbitrary
compression methods. They omit dependencies that a better model could exploit.

This limits the expected return from another simple frequency-counter tweak.
Larger weight savings would need additional structure, a different model size,
or changes to the model itself, with full prediction/package checks. Preserve
the small verified permutation lead, but do not mistake it for a winning margin.

Run with the isolated NumPy environment:

```sh
build/weight-audit-env/bin/python scripts/weight_audit.py --output build/weight-audit-next
```

The measurement preceded the observer's first commit; its exact source hash is
recorded in `report.json`, alongside the pinned writer hash and environment.
