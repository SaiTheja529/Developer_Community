import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react';
import { COMPONENT_LABELS } from '@/lib/modules';
import { Button } from '@/components/common/Button';
import { inputClass } from './Field';
import { cn } from '@/lib/cn';

const move = <T,>(arr: T[], i: number, d: number) => {
  const j = i + d;
  if (j < 0 || j >= arr.length) return arr;
  const n = [...arr];
  [n[i], n[j]] = [n[j], n[i]];
  return n;
};
const icon = 'grid size-8 cursor-pointer place-items-center rounded-[6px] text-muted hover:bg-surface-2 hover:text-text disabled:opacity-30';

export interface ComponentRow { type: string; name: string; description: string }

export function ComponentListEditor({ value, onChange, types, errors }: { value: ComponentRow[]; onChange: (v: ComponentRow[]) => void; types: string[]; errors: Record<string, string> }) {
  const upd = (i: number, patch: Partial<ComponentRow>) => onChange(value.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  return (
    <div>
      {value.length === 0 && <p className="rounded-[6px] border border-dashed border-border px-3 py-4 text-center text-sm text-muted">No components yet. Add the rules, hooks, subagents or MCP servers this harness uses.</p>}
      <ol className="space-y-3">
        {value.map((r, i) => (
          <li key={i} className="rounded-[10px] border border-border bg-bg p-3">
            <div className="flex flex-wrap items-start gap-2">
              <span className="pt-2 font-mono text-xs text-muted">{i + 1}</span>
              <label className="flex w-44 flex-col gap-1">
                <span className="text-xs font-medium text-muted">Type</span>
                <select value={r.type} onChange={(e) => upd(i, { type: e.target.value })} className={cn(inputClass, 'h-9 text-sm')}>
                  {types.map((t) => <option key={t} value={t}>{COMPONENT_LABELS[t]?.replace(/s$/, '') ?? t}</option>)}
                </select>
              </label>
              <label className="flex min-w-40 flex-1 flex-col gap-1">
                <span className="text-xs font-medium text-muted">Name (required)</span>
                <input value={r.name} maxLength={100} onChange={(e) => upd(i, { name: e.target.value })} aria-invalid={!!errors[`components.${i}.name`]} className={cn(inputClass, 'h-9 font-mono text-sm')} placeholder="pre-tool-check" />
              </label>
              <div className="ml-auto flex items-center pt-5">
                <button type="button" className={icon} disabled={i === 0} onClick={() => onChange(move(value, i, -1))} aria-label={`Move component ${i + 1} up`}><ArrowUp size={15} /></button>
                <button type="button" className={icon} disabled={i === value.length - 1} onClick={() => onChange(move(value, i, 1))} aria-label={`Move component ${i + 1} down`}><ArrowDown size={15} /></button>
                <button type="button" className={icon} onClick={() => onChange(value.filter((_, k) => k !== i))} aria-label={`Remove component ${i + 1}`}><Trash2 size={15} /></button>
              </div>
            </div>
            <label className="mt-2 flex flex-col gap-1 pl-5">
              <span className="text-xs font-medium text-muted">What it does</span>
              <input value={r.description} maxLength={2000} onChange={(e) => upd(i, { description: e.target.value })} className={cn(inputClass, 'h-9 text-sm')} placeholder="Blocks edits to files without a spec" />
            </label>
            {errors[`components.${i}.name`] && <p className="mt-1 pl-5 text-sm text-danger">{errors[`components.${i}.name`]}</p>}
          </li>
        ))}
      </ol>
      <Button type="button" size="sm" className="mt-3" disabled={value.length >= 50} onClick={() => onChange([...value, { type: types[0] ?? 'rule', name: '', description: '' }])}>
        <Plus size={14} aria-hidden /> Add component
      </Button>
    </div>
  );
}

export interface FeatureRow { title: string; detail: string }

export function FeatureListEditor({ value, onChange }: { value: FeatureRow[]; onChange: (v: FeatureRow[]) => void }) {
  const upd = (i: number, patch: Partial<FeatureRow>) => onChange(value.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  return (
    <div>
      <ol className="space-y-2">
        {value.map((r, i) => (
          <li key={i} className="flex flex-wrap items-start gap-2 rounded-[10px] border border-border bg-bg p-2.5">
            <input value={r.title} maxLength={150} onChange={(e) => upd(i, { title: e.target.value })} aria-label={`Feature ${i + 1} title`} placeholder="Feature" className={cn(inputClass, 'h-9 w-48 text-sm')} />
            <input value={r.detail} maxLength={2000} onChange={(e) => upd(i, { detail: e.target.value })} aria-label={`Feature ${i + 1} detail`} placeholder="Detail (optional)" className={cn(inputClass, 'h-9 min-w-40 flex-1 text-sm')} />
            <div className="flex">
              <button type="button" className={icon} disabled={i === 0} onClick={() => onChange(move(value, i, -1))} aria-label={`Move feature ${i + 1} up`}><ArrowUp size={15} /></button>
              <button type="button" className={icon} disabled={i === value.length - 1} onClick={() => onChange(move(value, i, 1))} aria-label={`Move feature ${i + 1} down`}><ArrowDown size={15} /></button>
              <button type="button" className={icon} onClick={() => onChange(value.filter((_, k) => k !== i))} aria-label={`Remove feature ${i + 1}`}><Trash2 size={15} /></button>
            </div>
          </li>
        ))}
      </ol>
      <Button type="button" size="sm" className="mt-3" disabled={value.length >= 30} onClick={() => onChange([...value, { title: '', detail: '' }])}>
        <Plus size={14} aria-hidden /> Add feature
      </Button>
    </div>
  );
}
