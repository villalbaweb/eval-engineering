# Capability versus regression evals

Regression evals guard behaviour that already works. They are fast, deterministic, code-heavy and should run on every change; the expected pass rate is close to 100 percent.

Capability evals probe the frontier with hard tasks. They start with a low pass rate, use several trials per task (k of 5 or more) and often an LLM judge. When a capability task becomes reliable it graduates into the regression suite.
