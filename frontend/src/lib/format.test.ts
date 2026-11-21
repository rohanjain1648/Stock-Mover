import { describe, it, expect } from "vitest";
import { inr, days, moveLabel, num, dash, shortDate, triggerLabel } from "./format";

describe("format", () => {
  it("inr", () => {
    expect(inr(12345)).toBe("₹12,345");
    expect(inr(250000)).toBe("₹2.5 L");
    expect(inr(31000000)).toBe("₹3.1 Cr");
    expect(inr(99999.6)).toBe("₹1,00,000");
    expect(inr(null)).toBe("—");
  });
  it("days", () => {
    expect(days(null)).toBe("∞");
    expect(days(12.4)).toBe("12 d");
  });
  it("labels", () => {
    expect(moveLabel("PULL_BACK")).toBe("Pull back");
    expect(moveLabel("WH_TO_STORE")).toBe("Warehouse → store");
    expect(moveLabel("STORE_TO_STORE")).toBe("Store → store");
  });
  it("num uses Indian grouping and dashes for missing values", () => {
    expect(num(1234567)).toBe("12,34,567");
    expect(num(null)).toBe("—");
    expect(num(Number.NaN)).toBe("—");
    expect(dash(null)).toBe("—");
    expect(dash(undefined)).toBe("—");
    expect(dash(0)).toBe("0");
  });
  it("dates and triggers", () => {
    expect(shortDate("2026-11-01")).toBe("1 Nov");
    expect(triggerLabel("schedule")).toBe("Scheduled 07:00");
    expect(triggerLabel("github")).toBe("GitHub");
    expect(triggerLabel("manual")).toBe("Manual");
  });
});
