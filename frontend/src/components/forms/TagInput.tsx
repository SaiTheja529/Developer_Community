import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { normalizeTag } from '@/lib/tags';
import { getData } from '@/lib/api/client';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { cn } from '@/lib/cn';

/** Chips. Enter/comma adds, Backspace removes, autocomplete from /api/tags (spec §10). */
export function TagInput({ id, value, onChange, max = 8, module, placeholder = 'Type and press Enter', invalid, describedBy }: {
  id?: string; value: string[]; onChange: (v: string[]) => void; max?: number; module?: string; placeholder?: string; invalid?: boolean; describedBy?: string;
}) {
  const [text, setText] = useState('');
  const dq = useDebouncedValue(text, 250);
  const [sugg, setSugg] = useState<string[]>([]);
  useEffect(() => {
    if (!module || dq.length < 1) { setSugg([]); return; }
    let live = true;
    getData<{ tag: string; count: number }[]>('/api/tags', { module, q: normalizeTag(dq), limit: 6 })
      .then((r) => live && setSugg(r.map((x) => x.tag).filter((t) => !value.includes(t))))
      .catch(() => live && setSugg([]));
    return () => { live = false; };
  }, [dq, module, value]);
  const add = (raw: string) => {
    const t = normalizeTag(raw);
    if (!t || value.includes(t) || value.length >= max) return;
    onChange([...value, t]);
    setText('');
    setSugg([]);
  };
  return (
    <div>
      <div className={cn('flex min-h-10 flex-wrap items-center gap-1.5 rounded-[6px] border bg-surface px-2 py-1.5 focus-within:outline-2 focus-within:outline-focus', invalid ? 'border-danger' : 'border-border')}>
        {value.map((t) => (
          <span key={t} className="inline-flex items-center gap-1 rounded-[6px] bg-surface-2 py-0.5 pr-1 pl-2 font-mono text-xs">
            {t}
            <button type="button" onClick={() => onChange(value.filter((x) => x !== t))} className="grid size-5 cursor-pointer place-items-center rounded hover:bg-border" aria-label={`Remove ${t}`}>
              <X size={12} />
            </button>
          </span>
        ))}
        <input
          id={id}
          value={text}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          disabled={value.length >= max}
          onChange={(e) => {
            if (e.target.value.endsWith(',')) add(e.target.value.slice(0, -1));
            else setText(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); add(text); }
            if (e.key === 'Backspace' && !text && value.length) onChange(value.slice(0, -1));
          }}
          onBlur={() => text && add(text)}
          placeholder={value.length >= max ? `Max ${max}` : placeholder}
          className="h-7 min-w-32 flex-1 bg-transparent font-mono text-sm outline-none placeholder:font-sans placeholder:text-muted"
        />
      </div>
      {sugg.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1" aria-label="Suggestions">
          {sugg.map((s) => (
            <button key={s} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => add(s)} className="cursor-pointer rounded-[6px] border border-border px-1.5 py-0.5 font-mono text-xs text-muted hover:text-text">+ {s}</button>
          ))}
        </div>
      )}
      <p className="mt-1 font-mono text-xs text-muted">{value.length} / {max}</p>
    </div>
  );
}
