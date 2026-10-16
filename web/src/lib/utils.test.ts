import { confidenceLevel, formatBytes, groupByRecency, parseTimestamp, sourceMeta } from "./utils";

describe("utils", () => {
  it("parses SQLite UTC timestamps", () => {
    expect(parseTimestamp("2026-10-16 10:00:00")?.toISOString()).toBe("2026-10-16T10:00:00.000Z");
    expect(parseTimestamp(null)).toBeNull();
  });

  it("groups sessions by recency", () => {
    const now = new Date("2026-10-16T12:00:00");
    const iso = (d: Date) => d.toISOString();
    const groups = groupByRecency(
      [
        { id: 1, last_active: iso(new Date("2026-10-16T09:00:00")) },
        { id: 2, last_active: iso(new Date("2026-10-15T09:00:00")) },
        { id: 3, last_active: iso(new Date("2026-10-12T09:00:00")) },
        { id: 4, last_active: iso(new Date("2026-01-01T09:00:00")) },
      ],
      now,
    );
    expect(groups.map((g) => [g.label, g.items.map((i) => i.id)])).toEqual([
      ["Today", [1]],
      ["Yesterday", [2]],
      ["Previous 7 days", [3]],
      ["Older", [4]],
    ]);
  });

  it("maps confidence to levels", () => {
    expect(confidenceLevel(0.9).label).toBe("High");
    expect(confidenceLevel(0.5).label).toBe("Medium");
    expect(confidenceLevel(0.1).label).toBe("Low");
  });

  it("labels sources", () => {
    expect(sourceMeta("aws_cost_explorer").label).toBe("Cost Explorer");
    expect(sourceMeta("knowledge_base").label).toBe("Knowledge base");
    expect(sourceMeta("aws_new_thing").label).toBe("New thing");
  });

  it("formats bytes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
  });
});
