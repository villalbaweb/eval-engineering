import { describe, expect, it } from "vitest";
import { pct, rateClass, signedPct } from "./format";

describe("format", () => {
  it("formats percentages and missing values", () => {
    expect(pct(0.625)).toBe("63%");
    expect(pct(0.625, 1)).toBe("62.5%");
    expect(pct(null)).toBe("–");
    expect(pct(NaN)).toBe("–");
  });
  it("signs deltas", () => {
    expect(signedPct(0.05)).toBe("+5.0%");
    expect(signedPct(-0.125)).toBe("-12.5%");
  });
  it("classifies rates", () => {
    expect(rateClass(0.95)).toBe("good");
    expect(rateClass(0.7)).toBe("warn");
    expect(rateClass(0.2)).toBe("bad");
  });
});
