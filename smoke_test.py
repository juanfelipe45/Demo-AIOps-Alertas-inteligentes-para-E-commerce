from aiops_demo import (
    generate_dataset, detect_static, detect_zscore, detect_cusum,
    detect_isolation_forest, build_alerts, deduplicate_alerts,
    correlate_alerts, evaluate_method
)

df = generate_dataset(seed=42, hours=24)
assert len(df) == 24 * 60 * 5
assert df["is_incident"].sum() > 0

methods = [
    detect_static(df),
    detect_zscore(df, window=60, threshold=2.7),
    detect_cusum(df),
    detect_isolation_forest(df, seed=42),
]
for flags in methods:
    ev = evaluate_method(df, flags)
    assert len(flags) == len(df)
    assert 0 <= ev["Precisión"] <= 1
    assert 0 <= ev["Recall"] <= 1
    assert 0 <= ev["F1"] <= 1

z = methods[1]
alerts = build_alerts(df, z, window=60, threshold=2.7)
dedup = deduplicate_alerts(alerts, window_minutes=5)
incidents = correlate_alerts(dedup, min_metrics=2, correlation_window_minutes=5)
assert len(alerts) >= len(dedup) >= len(incidents)
print("OK")
print("Filas:", len(df))
print("Alertas Z-score:", len(alerts))
print("Deduplicadas:", len(dedup))
print("Incidentes correlacionados:", len(incidents))
