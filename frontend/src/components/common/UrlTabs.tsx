import * as Tabs from '@radix-ui/react-tabs';
import { useSearchParams } from 'react-router';
import type { ReactNode } from 'react';

/** Radix tabs synced to `?tab=` (spec §11.1). */
export function UrlTabs({ tabs, color }: { tabs: { id: string; label: ReactNode; content: ReactNode }[]; color: string }) {
  const [sp, setSp] = useSearchParams();
  const value = sp.get('tab') ?? tabs[0].id;
  return (
    <Tabs.Root
      value={value}
      onValueChange={(v) =>
        setSp((p) => {
          const n = new URLSearchParams(p);
          if (v === tabs[0].id) n.delete('tab');
          else n.set('tab', v);
          return n;
        }, { replace: true })
      }
    >
      <Tabs.List className="flex gap-1 overflow-x-auto overflow-y-hidden border-b border-border [scrollbar-width:none]" aria-label="Sections">
        {tabs.map((t) => (
          <Tabs.Trigger
            key={t.id}
            value={t.id}
            className="relative -mb-px h-10 shrink-0 cursor-pointer border-b-2 border-transparent px-3 text-sm font-medium text-muted hover:text-text data-[state=active]:text-text"
            style={value === t.id ? { borderBottomColor: color } : undefined}
          >
            {t.label}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
      {tabs.map((t) => (
        <Tabs.Content key={t.id} value={t.id} className="pt-6 focus-visible:outline-none">
          {t.content}
        </Tabs.Content>
      ))}
    </Tabs.Root>
  );
}
