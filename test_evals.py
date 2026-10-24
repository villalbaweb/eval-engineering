import unittest

from evals import evaluate


class EvaluateTests(unittest.TestCase):
    def test_reports_exact_match_results_and_accuracy(self):
        examples = [
            {"input": "hello", "expected_output": "HELLO"},
            {"input": "world", "expected_output": "WORLD!"},
        ]

        result = evaluate(examples, str.upper)

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["passed"], 1)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(
            result["results"],
            [
                {
                    "input": "hello",
                    "expected_output": "HELLO",
                    "actual_output": "HELLO",
                    "passed": True,
                },
                {
                    "input": "world",
                    "expected_output": "WORLD!",
                    "actual_output": "WORLD",
                    "passed": False,
                },
            ],
        )

    def test_empty_dataset_has_zero_accuracy(self):
        result = evaluate([], str.upper)

        self.assertEqual(result["total"], 0)
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["accuracy"], 0.0)
        self.assertEqual(result["results"], [])


if __name__ == "__main__":
    unittest.main()
