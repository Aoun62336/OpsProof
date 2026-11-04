import { describe, expect, it } from "vitest";
import { isTerminal, shortId, titleCase } from "./format";

describe("OpsProof formatting utilities", () => {
  it("shortens experiment identifiers", () => {
    expect(shortId("12345678-aaaa-bbbb-cccc-000000000001")).toBe("12345678");
  });
  it("formats event identifiers for display", () => {
    expect(titleCase("jobs_processed")).toBe("Jobs Processed");
    expect(titleCase("queue-burst")).toBe("Queue Burst");
  });
  it("distinguishes terminal states", () => {
    expect(isTerminal("succeeded")).toBe(true);
    expect(isTerminal("failed")).toBe(true);
    expect(isTerminal("running")).toBe(false);
    expect(isTerminal("verifying")).toBe(false);
  });
});
