import type { GradeLite } from "@/shared/types";
import { Badge } from "@/shared/ui";

/** One grader verdict. Text + colour, never colour alone. */
export function GradeBadge({ g }: { g: Pick<GradeLite, "grader" | "passed" | "skipped"> }) {
  if (g.skipped) return <Badge kind="neutral">{g.grader}: skipped</Badge>;
  return <Badge kind={g.passed ? "good" : "bad"}>{g.grader}: {g.passed ? "pass" : "FAIL"}</Badge>;
}
