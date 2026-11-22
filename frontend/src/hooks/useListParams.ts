import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router';

const KEYS = ['q', 'category', 'tags', 'tools', 'tech', 'resource_type', 'level', 'official', 'collaboration_status', 'featured', 'include_broken', 'sort', 'page'] as const;
export type ListParamKey = (typeof KEYS)[number];
export type ListParams = Partial<Record<ListParamKey, string>>;

/** Filters + page live in the URL (spec §7.6). Changing any filter resets page to 1. */
export function useListParams(defaults: ListParams = {}) {
  const [sp, setSp] = useSearchParams();
  const params = useMemo(() => {
    const out: ListParams = { ...defaults };
    for (const k of KEYS) {
      const v = sp.get(k);
      if (v !== null) out[k] = v;
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp]);

  const set = useCallback(
    (patch: ListParams) => {
      setSp((prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(patch)) {
          if (v === undefined || v === '' || v === defaults[k as ListParamKey]) next.delete(k);
          else next.set(k, v);
        }
        if (!('page' in patch)) next.delete('page');
        return next;
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setSp],
  );
  const clear = useCallback(() => setSp(new URLSearchParams()), [setSp]);
  const activeCount = KEYS.filter((k) => k !== 'page' && k !== 'sort' && sp.get(k)).length;
  return { params, set, clear, activeCount, page: Number(params.page ?? 1) };
}
