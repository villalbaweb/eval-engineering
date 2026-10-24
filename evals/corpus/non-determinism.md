# Handling non-determinism

Run several trials per task and report the mean pass rate with a bootstrap confidence interval instead of a single result. Record and replay tool outputs so external services do not add noise, and set the model temperature to 0 when measuring regressions.

Use permissive trajectory matching (unordered or superset) when several tool orders are valid, otherwise harmless variation produces false failures.
