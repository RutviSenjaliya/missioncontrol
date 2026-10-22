import { describe, expect, it } from "vitest";
import { parseInline, parseMarkdown } from "./markdown";
import { isTerminal, statusTone, verificationLabel } from "./status";

describe("markdown", () => {
  it("parses headings, lists and paragraphs", () => {
    const b = parseMarkdown("# Title\n\nIntro **bold** text\n\n## Open Tasks\n\n- One (task #1)\n- Two");
    expect(b.map((x) => x.kind)).toEqual(["h1", "p", "h2", "ul"]);
    expect(b[3]).toEqual({ kind: "ul", items: [[{ text: "One (task #1)" }], [{ text: "Two" }]] });
  });
  it("never treats HTML as markup", () => {
    expect(parseMarkdown("<script>alert(1)</script>")).toEqual([{ kind: "p", parts: [{ text: "<script>alert(1)</script>" }] }]);
  });
  it("parses inline emphasis", () => {
    expect(parseInline("_None recorded._")).toEqual([{ text: "None recorded.", italic: true }]);
  });
});

describe("status helpers", () => {
  it("maps statuses honestly", () => {
    expect(statusTone("completed")).toBe("good");
    expect(statusTone("partially_completed")).toBe("partial");
    expect(isTerminal("awaiting_approval")).toBe(false);
    expect(verificationLabel(null)).toBe("Not verified");
  });
});
