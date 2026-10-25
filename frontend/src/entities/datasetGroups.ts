import type { Catalog } from "@/shared/types";

/** Suites whose `datasets:` select this group (by folder name or a path inside it). */
export function suitesUsing(c: Catalog | undefined, group: string): string[] {
  if (!c || !group) return [];
  return c.suites.filter((s) => s.datasets.some((d) => d === group || d.startsWith(`${group}/`))).map((s) => s.name);
}

/** Link to the launch form, pre-filled to run `group` with `suite` as the template. */
export function runGroupHref(group: string, suite?: string): string {
  const q = new URLSearchParams({ datasets: group });
  if (suite) q.set("suite", suite);
  return `/experiments?${q}`;
}

/** Imported traces carry their transcript: the free `traces` suite (trace target) grades them as logged. */
export const suggestedSuite = (hasTranscripts: boolean) => (hasTranscripts ? "traces" : "smoke");
