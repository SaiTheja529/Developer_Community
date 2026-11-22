import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/cn';
import { MODULES, type ModuleKey } from '@/lib/modules';

export function PageHeader({ module, crumbs, title, badges, meta, actions }: {
  module: ModuleKey; crumbs?: { to: string; label: string }[]; title: ReactNode; badges?: ReactNode; meta?: ReactNode; actions?: ReactNode;
}) {
  return (
    <header className={cn('border-b border-border bg-surface', `stripe-${module}`)}>
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-8">
        {crumbs && (
          <nav aria-label="Breadcrumb" className="mb-3">
            <ol className="flex flex-wrap items-center gap-1 text-sm text-muted">
              {crumbs.map((c, i) => (
                <li key={c.to} className="inline-flex items-center gap-1">
                  {i > 0 && <ChevronRight size={13} aria-hidden />}
                  <Link to={c.to} className="hover:text-text hover:underline">{c.label}</Link>
                </li>
              ))}
            </ol>
          </nav>
        )}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-[26px] md:text-[30px]">{title}</h1>
              {badges}
            </div>
            {meta && <div className="mt-2">{meta}</div>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      </div>
    </header>
  );
}

export function ModuleHero({ module, cta }: { module: ModuleKey; cta?: ReactNode }) {
  const m = MODULES[module];
  const Icon = m.icon;
  return (
    <section className={cn('relative overflow-hidden border-b border-border bg-surface', `stripe-${module}`)}>
      <div className="dot-grid absolute inset-0 opacity-60 [mask-image:linear-gradient(to_left,black,transparent_70%)]" aria-hidden />
      <div className="relative mx-auto flex max-w-[1200px] flex-col gap-5 px-4 py-10 md:flex-row md:items-end md:justify-between md:px-8">
        <div className="max-w-2xl">
          <p className="flex items-center gap-2 font-mono text-sm" style={{ color: m.color }}>
            <Icon size={16} aria-hidden /> {m.tagline}
          </p>
          <h1 className="mt-2 text-[30px] md:text-[36px]">{m.name}</h1>
          <p className="mt-2 text-muted">{m.explainer}</p>
        </div>
        {cta}
      </div>
    </section>
  );
}
