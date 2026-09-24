import { describe, expect, it } from "vitest";
import { entityHref, linkifyMarkdown, parseEntityHref } from "../utils/linkify";

const T = [
  { id: "demo.A", names: ["A"] },
  { id: "p.CasingService", names: ["CasingService"] },
  { id: "p.CasingService.processClaims", names: ["CasingService.processClaims"] },
];

describe("linkifyMarkdown", () => {
  it("links chains of entity names", () => {
    const out = linkifyMarkdown("A → B", T);
    expect(out).toBe(`[A](${entityHref("demo.A")}) → B`);
  });

  it("prefers the longest name and keeps backticks and parens", () => {
    const out = linkifyMarkdown("Call `CasingService.processClaims()` now", T);
    expect(out).toBe(`Call [\`CasingService.processClaims()\`](${entityHref("p.CasingService.processClaims")}) now`);
  });

  it("does not match inside other identifiers", () => {
    expect(linkifyMarkdown("MyCasingServiceX and CasingService.other", T)).toBe("MyCasingServiceX and CasingService.other");
  });

  it("leaves code fences and existing links alone", () => {
    const md = "```\nA calls\n```\n[A](http://x)";
    expect(linkifyMarkdown(md, T)).toBe(md);
  });

  it("links overloaded Java2OKF titles with parameter lists", () => {
    const t = [{ id: "java-method:p.S.place(p.C,double)", names: ["S.place(C, double)", "S.place"] }];
    expect(linkifyMarkdown("see S.place(C, double) and `S.place`", t)).toBe(
      `see [S.place(C, double)](${entityHref("java-method:p.S.place(p.C,double)")}) and [\`S.place\`](${entityHref("java-method:p.S.place(p.C,double)")})`);
  });

  it("round-trips ids through hrefs", () => {
    expect(parseEntityHref(entityHref("a.b.C$1"))).toBe("a.b.C$1");
    expect(parseEntityHref("https://x")).toBeNull();
  });
});
