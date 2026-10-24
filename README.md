# eval-engineering

A hands-on starting point for exploring and learning evaluation engineering: the practice of measuring system behavior with representative examples, explicit criteria, and repeatable runs.

## First example

This repository includes a small, dependency-free exact-match evaluator. Each example has an `input` and an `expected_output`; a prediction function produces the actual output. The evaluator returns per-example results and an aggregate accuracy score.

```python
from evals import evaluate

examples = [
    {"input": "hello", "expected_output": "HELLO"},
    {"input": "world", "expected_output": "WORLD"},
]

report = evaluate(examples, str.upper)
print(report["accuracy"])  # 1.0
```

Run the tests with Python's built-in test runner:

```sh
python -m unittest -v
```

## Learning path

Use this small baseline to explore how evaluation workflows grow:

1. Build representative datasets, including difficult and failure cases.
2. Define clear criteria and choose metrics that match the task.
3. Run a baseline and inspect individual results, not only aggregate scores.
4. Change the system, rerun the same dataset, and compare results.
5. Track limitations such as dataset coverage and exact-match scoring.

The exact-match metric here is deliberately simple; it is a teaching example, not a complete evaluation framework.
