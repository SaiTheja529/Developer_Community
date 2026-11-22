import { useCallback, useEffect, useRef, useState } from 'react';
import { useBlocker } from 'react-router';
import { ApiError } from '@/lib/api/client';

/** Lightweight controlled-form state with backend error mapping (spec §12). */
export function useForm<T extends Record<string, unknown>>(initial: T) {
  const [values, setValues] = useState<T>(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const set = useCallback(<K extends keyof T>(k: K, v: T[K]) => {
    setValues((s) => ({ ...s, [k]: v }));
    setDirty(true);
    setErrors((e) => {
      if (!e[k as string]) return e;
      const n = { ...e };
      delete n[k as string];
      return n;
    });
  }, []);
  const reset = useCallback((v: T) => { setValues(v); setDirty(false); setErrors({}); }, []);
  /** Returns true when the error was a field-level validation error and has been mapped. */
  const applyApiError = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.code === 'validation_error' && e.details?.fields) {
      setErrors(e.details.fields as Record<string, string>);
      requestAnimationFrame(() => document.getElementById('error-summary')?.focus());
      return true;
    }
    return false;
  }, []);
  return { values, set, setValues, errors, setErrors, dirty, setDirty, reset, applyApiError };
}

/** Saves the form to localStorage every 2 s while dirty, and offers a restore (spec §11.1, §12). */
export function useFormAutosave<T>(key: string, values: T, dirty: boolean, enabled = true) {
  const storageKey = `form:${key}`;
  const [saved] = useState<T | null>(() => {
    if (!enabled) return null;
    try {
      const raw = localStorage.getItem(storageKey);
      return raw ? (JSON.parse(raw) as T) : null;
    } catch {
      return null;
    }
  });
  const latest = useRef(values);
  latest.current = values;
  useEffect(() => {
    if (!dirty || !enabled) return;
    const t = setTimeout(() => {
      try {
        localStorage.setItem(storageKey, JSON.stringify(latest.current));
      } catch {
        /* storage full or blocked */
      }
    }, 2000);
    return () => clearTimeout(t);
  }, [values, dirty, enabled, storageKey]);
  const clear = useCallback(() => {
    try {
      localStorage.removeItem(storageKey);
    } catch {
      /* ignore */
    }
  }, [storageKey]);
  return { saved, clear };
}

/** Blocks in-app navigation and tab close while there are unsaved changes. */
export function useUnsavedChangesGuard(when: boolean) {
  const bypassed = useRef(false);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => !bypassed.current && when && currentLocation.pathname !== nextLocation.pathname);
  useEffect(() => {
    if (blocker.state === 'blocked') {
      if (window.confirm('You have unsaved changes. Leave this page?')) blocker.proceed();
      else blocker.reset();
    }
  }, [blocker]);
  useEffect(() => {
    if (!when) return;
    const f = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener('beforeunload', f);
    return () => window.removeEventListener('beforeunload', f);
  }, [when]);
  /** Call right before navigating away after a successful save or delete. */
  return useCallback(() => { bypassed.current = true; }, []);
}
