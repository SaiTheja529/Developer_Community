import { useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { ApiError } from '@/lib/api/client';
import { ErrorState } from './States';
import { buttonClass } from './Button';
import { EyeOff } from 'lucide-react';

/** Replace-navigate to the canonical slug once data loads (spec §9). */
export function useCanonicalSlug(base: string, id: string | undefined, slug: string | undefined) {
  const params = useParams();
  const navigate = useNavigate();
  useEffect(() => {
    if (id && slug && params.slug !== slug) navigate(`${base}/${id}/${slug}${location.search}`, { replace: true });
  }, [id, slug, params.slug, base, navigate]);
}

export function DetailError({ error, retry, noun, listPath }: { error: unknown; retry: () => void; noun: string; listPath: string }) {
  if (error instanceof ApiError && error.status === 404)
    return (
      <div className="mx-auto max-w-[720px] px-4 py-20 text-center">
        <p className="font-mono text-sm text-muted">404</p>
        <h1 className="mt-2 text-2xl">This {noun} doesn't exist or was removed.</h1>
        <Link to={listPath} className={buttonClass('secondary', 'md', 'mt-6')}>Browse all</Link>
      </div>
    );
  return <div className="mx-auto max-w-[720px] px-4 py-16"><ErrorState error={error} onRetry={retry} /></div>;
}

export function HiddenBanner({ status }: { status: string }) {
  if (status === 'published') return null;
  return (
    <div role="status" className="flex items-center gap-2 border-b border-warning bg-warning-soft px-4 py-2 text-sm md:px-8">
      <EyeOff size={15} className="text-warning" aria-hidden /> Hidden by moderators. Only you and moderators can see this.
    </div>
  );
}

export function Section({ title, children, id }: { title: string; children: React.ReactNode; id?: string }) {
  return (
    <section id={id} className="mt-8 first:mt-0">
      <h2 className="mb-3 text-lg">{title}</h2>
      {children}
    </section>
  );
}

export function SideCard({ title, children, className }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-[10px] border border-border bg-surface p-4 ${className ?? ''}`}>
      {title && <p className="mb-3 text-sm font-semibold">{title}</p>}
      {children}
    </div>
  );
}
