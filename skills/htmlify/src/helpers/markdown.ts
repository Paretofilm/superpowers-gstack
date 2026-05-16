import { marked, type Tokens } from "marked";
import DOMPurify from "isomorphic-dompurify";

export type Token = Tokens.Generic;

// Tokenize MD source via marked.lexer() (per design — section-level routing).
export function tokenize(md: string): Token[] {
  return marked.lexer(md) as Token[];
}

// Extract a section by H2 heading text. Returns tokens between the matching H2
// and the next H2 (or end of doc). Returns null if heading not found.
// Duplicate headings: first occurrence wins (per design).
export function extractSection(tokens: Token[], heading: string): Token[] | null {
  const norm = heading.trim().toLowerCase();
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (
      t.type === "heading" &&
      (t as Tokens.Heading).depth === 2 &&
      (t as Tokens.Heading).text.trim().toLowerCase() === norm
    ) {
      const out: Token[] = [];
      for (let j = i + 1; j < tokens.length; j++) {
        const next = tokens[j];
        if (next.type === "heading" && (next as Tokens.Heading).depth === 2) break;
        out.push(next);
      }
      return out;
    }
  }
  return null;
}

// Render tokens to sanitized HTML. Body sanitization per D4 (Codex #12).
// DOMPurify strips <script>, on* handlers, etc. while keeping safe markdown
// constructs (em, strong, code, lists, etc.).
export function renderTokens(tokens: Token[]): string {
  const raw = marked.parser(tokens as Tokens.Token[]);
  return DOMPurify.sanitize(raw);
}

export function renderFullBody(md: string): string {
  const raw = marked.parse(md, { async: false }) as string;
  return DOMPurify.sanitize(raw);
}
