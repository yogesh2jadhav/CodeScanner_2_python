/**
 * Turn mentions of known entities in answer Markdown into links (#entity=<id>).
 *
 * Why client-side linkification: the backend returns the evidence set; any text
 * (deterministic answer or LLM output) that names one of those entities becomes
 * traceable to it, without trusting the LLM to produce well-formed links.
 */
export interface LinkTarget {
  id: string;
  names: string[];
}

export const ENTITY_HREF_PREFIX = "#entity=";

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function entityHref(id: string): string {
  return ENTITY_HREF_PREFIX + encodeURIComponent(id);
}

export function parseEntityHref(href: string | undefined | null): string | null {
  if (!href || !href.startsWith(ENTITY_HREF_PREFIX)) return null;
  try {
    return decodeURIComponent(href.slice(ENTITY_HREF_PREFIX.length));
  } catch {
    return null;
  }
}

export function linkifyMarkdown(markdown: string, targets: LinkTarget[]): string {
  const lookup = new Map<string, string>();
  for (const t of targets) {
    for (const n of [t.id, ...t.names]) {
      if (n && !lookup.has(n)) lookup.set(n, t.id);
    }
  }
  if (!lookup.size) return markdown;
  // Longest names first so "CasingService.processClaims" wins over "CasingService".
  const names = [...lookup.keys()].sort((a, b) => b.length - a.length).map(escapeRe);
  const re = new RegExp(`(\`?)(?<![\\w.$])(${names.join("|")})(\\(\\))?(?![\\w$]|\\.[A-Za-z_])\\1`, "g");

  // Leave fenced code blocks and existing links untouched.
  return markdown
    .split(/(```[\s\S]*?```)/g)
    .map((segment) => {
      if (segment.startsWith("```")) return segment;
      return segment
        .split(/(\[[^\]]*\]\([^)]*\))/g)
        .map((part) => {
          if (/^\[[^\]]*\]\([^)]*\)$/.test(part)) return part;
          return part.replace(re, (match, tick: string, name: string, parens: string | undefined) => {
            const id = lookup.get(name);
            if (!id) return match;
            const text = `${tick}${name}${parens ?? ""}${tick}`;
            return `[${text}](${entityHref(id)})`;
          });
        })
        .join("");
    })
    .join("");
}
