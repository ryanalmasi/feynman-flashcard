import { globSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const FORBIDDEN: RegExp[] = [
  /\b(?:bg|text|border|ring|outline|fill|stroke|from|via|to|divide|placeholder|decoration|shadow|accent|caret)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black|white)(?:-\d{2,3})?(?:\/\d+)?\b/,
  /#[0-9a-fA-F]{3,8}\b/,
  /\b(?:rgb|rgba|hsl|hsla|oklch)\(/,
  /style=\{\{[^}]*colou?r/i,
];

function violations(source: string): string[] {
  return FORBIDDEN.flatMap((re) => {
    const m = re.exec(source);
    return m ? [m[0]] : [];
  });
}

describe("design tokens", () => {
  it("screens use semantic token classes only", () => {
    const files = [
      ...globSync("src/pages/**/*.tsx"),
      ...globSync("src/components/*.tsx"),
      ...globSync("src/auth/**/*.tsx"),
      "src/App.tsx",
    ];
    const bad = files.flatMap((f) =>
      violations(readFileSync(f, "utf8")).map((m) => `${f}: ${m}`),
    );
    expect(bad).toEqual([]);
  });

  it("the checker catches raw colours", () => {
    expect(violations('className="bg-indigo-600"')).toHaveLength(1);
    expect(violations("color: #fff")).toHaveLength(1);
    expect(violations("oklch(0.5 0 0)")).toHaveLength(1);
    expect(violations('className="bg-primary text-muted-foreground"')).toEqual(
      [],
    );
  });
});
