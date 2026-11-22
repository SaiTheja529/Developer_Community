import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { ExternalLink } from 'lucide-react';
import { cn } from '@/lib/cn';
import { domainOf, safeUrl } from '@/lib/format';

/** Sanitized Markdown. Raw HTML disabled; images rendered as links (spec §10). */
export default function MarkdownImpl({ source, className }: { source: string; className?: string }) {
  return (
    <div className={cn('prose-dc', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        skipHtml
        components={{
          a: ({ href, children }) => {
            const url = safeUrl(href);
            if (!url) return <span>{children}</span>;
            return (
              <a href={url} target="_blank" rel="noopener noreferrer nofollow ugc">
                {children}
                <ExternalLink size={11} className="ml-0.5 inline align-baseline" aria-hidden />
                <span className="sr-only"> (opens {domainOf(url)} in a new tab)</span>
              </a>
            );
          },
          img: ({ src, alt }) => {
            const url = safeUrl(typeof src === 'string' ? src : undefined);
            return url ? <a href={url} target="_blank" rel="noopener noreferrer nofollow ugc">[image: {alt || domainOf(url)}]</a> : null;
          },
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
