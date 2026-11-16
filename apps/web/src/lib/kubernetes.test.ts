import { describe, expect, it } from "vitest";
import { requestShare, timestampIsFresh } from "./kubernetes";

describe("configured Kubernetes resource shares", () => {
  it.each([
    ["25m", "350m", 100 / 14],
    ["0.025", "350m", 100 / 14],
    ["72Mi", "256Mi", 28.125],
    ["512Mi", "1Gi", 50],
    ["5e5", "1M", 50],
    ["100u", "1m", 10],
    ["0", "1", 0],
  ])("compares %s with %s in matching units", (request, limit, expected) => {
    expect(requestShare(request, limit)).toBeCloseTo(expected);
  });
  it.each([
    [undefined, "1"],
    ["25m", undefined],
    ["1", "0"],
    ["-1", "1"],
    ["garbage", "1"],
    ["1e999", "1"],
    ["1", "1wrong"],
  ])("keeps unavailable or invalid reservations unknown", (request, limit) => {
    expect(requestShare(request, limit)).toBeNull();
  });
  it("rejects stale, future and invalid timestamps", () => {
    expect(timestampIsFresh(90, 100, 10)).toBe(true);
    expect(timestampIsFresh(89, 100, 10)).toBe(false);
    expect(timestampIsFresh(101, 100, 10)).toBe(false);
    expect(timestampIsFresh(NaN, 100, 10)).toBe(false);
  });
});
