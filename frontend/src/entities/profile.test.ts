import { describe, expect, it } from "vitest";
import { getProfile, profileHeaders, setProfile } from "@/shared/profile";
import type { ProfileView } from "@/shared/types";
import { suggestedSuite } from "./datasetGroups";
import { can, findVariant } from "./profile";

const demo = {
  name: "demo", default_variant: "prod-traces",
  variants: [
    { name: "prod-traces", target: "trace_source", aliases: [], capabilities: [] },
    { name: "staging", target: "http_agent", aliases: ["stage"], capabilities: ["chat", "rerun"] },
  ],
  defaults: { quick_suite: "regression", trace_suite: "prod", trace_group: "logged", langsmith_prefix: null },
} as unknown as ProfileView;

describe("profile capabilities", () => {
  it("finds variants by name, alias or default", () => {
    expect(findVariant(demo)?.name).toBe("prod-traces");
    expect(findVariant(demo, "stage")?.name).toBe("staging");
    expect(findVariant(demo, "nope")).toBeUndefined();
  });
  it("gates features on the variant", () => {
    expect(can(demo, null, "chat")).toBe(false);  // default variant is read-only
    expect(can(demo, "staging", "chat")).toBe(true);
    expect(can(demo, "staging", "fault_injection")).toBe(false);
    expect(can(undefined, "anything", "fault_injection")).toBe(true);  // older server: everything, as before
  });
  it("suggests the profile's own suites", () => {
    expect(suggestedSuite(true, demo.defaults)).toBe("prod");
    expect(suggestedSuite(false, demo.defaults)).toBe("regression");
  });
});

describe("profile header", () => {
  it("is sent only when a profile was chosen", () => {
    setProfile(null);
    expect(profileHeaders()).toEqual({});
    setProfile("demo");
    expect(getProfile()).toBe("demo");
    expect(profileHeaders()).toEqual({ "X-Eval-Profile": "demo" });
    setProfile(null);
  });
});
