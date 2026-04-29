import { describe, expect, it } from "vitest";
import { cn, formatCorrelationId, formatDurationMs, formatTimestamp } from "./utils";

describe("cn", () => {
  it("merges class names and resolves conflicts", () => {
    expect(cn("p-1", "p-2")).toBe("p-2");
    expect(cn("text-text", false && "hidden", "font-medium")).toBe(
      "text-text font-medium",
    );
  });
});

describe("formatTimestamp", () => {
  it("returns an em dash for null and undefined", () => {
    expect(formatTimestamp(null)).toBe("—");
    expect(formatTimestamp(undefined)).toBe("—");
  });

  it("formats ISO strings as DD/MM/YYYY HH:MM:SS", () => {
    const result = formatTimestamp("2026-04-29T09:00:00Z");
    expect(result).toMatch(/^\d{2}\/\d{2}\/2026 \d{2}:\d{2}:\d{2}$/);
  });
});

describe("formatCorrelationId", () => {
  it("truncates long IDs with an ellipsis", () => {
    expect(formatCorrelationId("corr-9f3a14b1c0d8")).toBe("corr-9f3…");
  });

  it("leaves short IDs alone", () => {
    expect(formatCorrelationId("abc")).toBe("abc");
  });

  it("handles missing values", () => {
    expect(formatCorrelationId(undefined)).toBe("—");
  });
});

describe("formatDurationMs", () => {
  it("formats sub-second values in ms", () => {
    expect(formatDurationMs(420)).toBe("420ms");
  });

  it("formats seconds with two decimals", () => {
    expect(formatDurationMs(1820)).toBe("1.82s");
  });

  it("formats minutes and seconds", () => {
    expect(formatDurationMs(125_000)).toBe("2m 5s");
  });
});
