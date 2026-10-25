import { describe, expect, it } from "vitest";
import type { Catalog } from "@/shared/types";
import { runGroupHref, suggestedSuite, suitesUsing } from "./datasetGroups";

const catalog = {
  suites: [
    { name: "smoke", datasets: ["skill-selection", "tool-use"] },
    { name: "traces", datasets: ["traces"] },
    { name: "picky", datasets: ["tool-use/basic.yaml"] },
  ],
} as unknown as Catalog;

describe("dataset groups", () => {
  it("finds suites by group name or a path inside the group", () => {
    expect(suitesUsing(catalog, "tool-use")).toEqual(["smoke", "picky"]);
    expect(suitesUsing(catalog, "accepted")).toEqual([]);
    expect(suitesUsing(undefined, "traces")).toEqual([]);
  });
  it("builds a pre-filled launch link", () => {
    expect(runGroupHref("accepted", "traces")).toBe("/experiments?datasets=accepted&suite=traces");
    expect(runGroupHref("accepted")).toBe("/experiments?datasets=accepted");
  });
  it("suggests the free trace-grading suite for logged traces", () => {
    expect(suggestedSuite(true)).toBe("traces");
    expect(suggestedSuite(false)).toBe("smoke");
  });
});
