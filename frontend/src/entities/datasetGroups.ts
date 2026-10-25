import type { Catalog, ProfileView } from "@/shared/types";

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

/** Imported traces carry their transcript: the profile's trace suite grades them as logged; tasks with
 * expectations go to its quick suite. Without profile info: the copilot's `traces` / `smoke`. */
export const suggestedSuite = (hasTranscripts: boolean, defaults?: ProfileView["defaults"]) =>
  hasTranscripts ? defaults?.trace_suite ?? "traces" : defaults?.quick_suite ?? "smoke";
