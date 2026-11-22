import { Color } from 'three';
import { cssVar } from '@/hooks/useTheme';

export interface Palette {
  dark: boolean;
  board: string; boardEdge: string; surface: string; border: string; text: string; muted: string;
  harness: string; idea: string; knowledge: string; ai: string; success: string; danger: string;
}

export function readPalette(dark: boolean): Palette {
  return {
    dark,
    board: cssVar('--board-top'), boardEdge: cssVar('--board-edge'), surface: cssVar('--surface'), border: cssVar('--border'),
    text: cssVar('--text'), muted: cssVar('--text-muted'),
    harness: cssVar('--harness'), idea: cssVar('--idea'), knowledge: cssVar('--knowledge'), ai: cssVar('--ai'),
    success: cssVar('--success'), danger: cssVar('--danger'),
  };
}

/** Mix two CSS colours in linear space, returning a hex string. */
export function mix(a: string, b: string, t: number) {
  return '#' + new Color(a).lerp(new Color(b), t).getHexString();
}

/** Deterministic 0..1 pseudo-random from a string (stable layout per item). */
export function hash01(s: string, salt = 0) {
  let h = 2166136261 ^ salt;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 10000) / 10000;
}
