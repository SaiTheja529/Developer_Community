import { useId, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react';
import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/cn';

export const inputClass =
  'w-full rounded-[6px] border border-border bg-surface px-3 text-[15px] text-text placeholder:text-muted aria-[invalid=true]:border-danger';

interface FieldProps {
  label: string;
  required?: boolean;
  hint?: ReactNode;
  error?: string;
  counter?: { n: number; max: number };
  children: (props: { id: string; 'aria-invalid'?: boolean; 'aria-describedby'?: string }) => ReactNode;
  className?: string;
}

/** Visible label, "(required)" in text, hint under the label, error linked via aria-describedby (spec §12). */
export function Field({ label, required, hint, error, counter, children, className }: FieldProps) {
  const id = useId();
  const describedBy = [hint ? `${id}-hint` : '', error ? `${id}-err` : ''].filter(Boolean).join(' ') || undefined;
  const pct = counter ? counter.n / counter.max : 0;
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-sm font-medium">
          {label} {required && <span className="font-normal text-muted">(required)</span>}
        </label>
        {counter && (
          <span className={cn('font-mono text-xs', pct > 1 ? 'text-danger' : pct >= 0.9 ? 'text-warning' : 'text-muted')}>
            {counter.n} / {counter.max}
          </span>
        )}
      </div>
      {hint && <p id={`${id}-hint`} className="-mt-0.5 text-xs text-muted">{hint}</p>}
      {children({ id, 'aria-invalid': error ? true : undefined, 'aria-describedby': describedBy })}
      {error && (
        <p id={`${id}-err`} className="flex items-start gap-1 text-sm text-danger">
          <AlertCircle size={14} className="mt-0.5 shrink-0" aria-hidden /> {error}
        </p>
      )}
    </div>
  );
}

export const TextInput = (p: InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={cn(inputClass, 'h-10', p.className)} />;
export const TextArea = (p: TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...p} className={cn(inputClass, 'min-h-24 resize-y py-2 leading-relaxed', p.className)} />;
export const SelectInput = ({ options, placeholder, ...p }: SelectHTMLAttributes<HTMLSelectElement> & { options: { value: string; label: string }[]; placeholder?: string }) => (
  <select {...p} className={cn(inputClass, 'h-10 pr-8', p.className)}>
    {placeholder !== undefined && <option value="">{placeholder}</option>}
    {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
);

export function Switch({ checked, onChange, label, description }: { checked: boolean; onChange: (v: boolean) => void; label: string; description?: string }) {
  const id = useId();
  return (
    <div className="flex items-start gap-3">
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn('relative mt-0.5 h-6 w-10 shrink-0 cursor-pointer rounded-full border transition-colors', checked ? 'border-text bg-text' : 'border-border bg-surface-2')}
      >
        <span className={cn('absolute top-0.5 size-[18px] rounded-full bg-bg shadow transition-[left]', checked ? 'left-[18px]' : 'left-0.5')} />
      </button>
      <label htmlFor={id} className="cursor-pointer">
        <span className="text-sm font-medium">{label}</span>
        {description && <span className="block text-xs text-muted">{description}</span>}
      </label>
    </div>
  );
}

export function FormSection({ id, title, description, children }: { id: string; title: string; description?: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-20 rounded-[10px] border border-border bg-surface p-5 md:p-6">
      <h2 id={`${id}-h`} className="text-lg">{title}</h2>
      {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      <div className="mt-5 flex flex-col gap-5">{children}</div>
    </section>
  );
}

export function ErrorSummary({ errors, labels }: { errors: Record<string, string>; labels: Record<string, string> }) {
  const entries = Object.entries(errors);
  if (!entries.length) return null;
  return (
    <div role="alert" tabIndex={-1} id="error-summary" className="rounded-[10px] border border-danger bg-danger-soft p-4 text-sm">
      <p className="font-medium text-danger">Fix {entries.length === 1 ? 'this field' : `these ${entries.length} fields`} before submitting:</p>
      <ul className="mt-2 list-disc pl-5">
        {entries.map(([k, v]) => <li key={k}><span className="font-medium">{labels[k.split('.')[0]] ?? k}</span>: {v}</li>)}
      </ul>
    </div>
  );
}
