from collections.abc import Callable, Iterable, Mapping


def evaluate(
    examples: Iterable[Mapping[str, str]],
    predict: Callable[[str], str],
) -> dict[str, object]:
    """Run a prediction function over examples and score exact matches."""
    results = []
    for example in examples:
        actual = predict(example["input"])
        expected = example["expected_output"]
        results.append(
            {
                "input": example["input"],
                "expected_output": expected,
                "actual_output": actual,
                "passed": actual == expected,
            }
        )

    passed = sum(result["passed"] for result in results)
    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "accuracy": passed / total if total else 0.0,
        "results": results,
    }
