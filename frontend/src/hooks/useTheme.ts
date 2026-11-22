import { useCallback, useEffect, useState } from 'react';

type Theme = 'light' | 'dark';
const media = () => window.matchMedia('(prefers-color-scheme: dark)');

function current(): Theme {
  const t = document.documentElement.dataset.theme;
  if (t === 'light' || t === 'dark') return t;
  return media().matches ? 'dark' : 'light';
}

/** Resolved theme, reactive to the toggle and to the OS preference. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(current);
  useEffect(() => {
    const update = () => setTheme(current());
    const m = media();
    m.addEventListener('change', update);
    window.addEventListener('dc:theme', update);
    return () => {
      m.removeEventListener('change', update);
      window.removeEventListener('dc:theme', update);
    };
  }, []);
  const toggle = useCallback(() => {
    const next: Theme = current() === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem('dc-theme', next);
    } catch {
      /* storage unavailable */
    }
    window.dispatchEvent(new Event('dc:theme'));
  }, []);
  return { theme, toggle };
}

/** Reads a CSS custom property's resolved value (used to feed the 3D scene). */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const m = window.matchMedia('(prefers-reduced-motion: reduce)');
    const f = () => setReduced(m.matches);
    m.addEventListener('change', f);
    return () => m.removeEventListener('change', f);
  }, []);
  return reduced;
}
