import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { useEntityPanel } from "./EntityPanelContext";
import { parseEntityHref } from "../utils/linkify";

/**
 * Markdown renderer for untrusted OKF/LLM content.
 * react-markdown never renders raw HTML (no rehype-raw), and URLs pass through
 * defaultUrlTransform (blocks javascript: etc.), so the output is sanitized.
 */
interface Props {
  children: string;
  className?: string;
  /** Relative OKF href -> entity id, so cross-document links open the entity panel. */
  linkTargets?: Record<string, string>;
}

export function Markdown({ children, className = "", linkTargets }: Props) {
  const { open } = useEntityPanel();
  return (
    <div className={`prose-ck ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => (parseEntityHref(url) ? url : defaultUrlTransform(url))}
        components={{
          a: ({ href, children: kids }) => {
            const entityId = parseEntityHref(href) ?? (href ? linkTargets?.[href] : undefined);
            if (entityId) {
              return (
                <button type="button" className="entity-ref font-medium text-blue-700 hover:underline dark:text-blue-300"
                  onClick={() => open(entityId)} title={entityId}>
                  {kids}
                </button>
              );
            }
            // OKF-relative links are not browsable pages; show them as text.
            if (href && !/^https?:\/\//.test(href)) return <span className="underline decoration-dotted">{kids}</span>;
            return <a href={href} target="_blank" rel="noopener noreferrer nofollow">{kids}</a>;
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
