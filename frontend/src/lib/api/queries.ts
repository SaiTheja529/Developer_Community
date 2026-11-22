import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch, getData } from './client';
import type {
  CollectionDetail, CollectionSummary, Comment, HarnessDetail, HarnessSummary, HomeData, IdeaDetail, IdeaSummary,
  Paginated, PublicProfile, ResourceDetail, ResourceSummary, Review, SearchResults, Suggestion,
} from './types';
import { qk } from '../queryKeys';
import { TARGET, type TargetType } from '../modules';

export const useHome = () => useQuery({ queryKey: qk.home, queryFn: () => getData<HomeData>('/api/home') });

function useList<T>(plural: string, params: object) {
  return useQuery({
    queryKey: qk.list(plural, params),
    queryFn: () => apiFetch<Paginated<T>>(`/api/${plural}`, { query: { page_size: 12, ...params } }),
    placeholderData: keepPreviousData,
  });
}
export const useHarnessList = (p: object) => useList<HarnessSummary>('harnesses', p);
export const useIdeaList = (p: object) => useList<IdeaSummary>('ideas', p);
export const useResourceList = (p: object) => useList<ResourceSummary>('resources', p);
export const useCollectionList = (p: object) => useList<CollectionSummary>('collections', p);

function useDetail<T>(plural: string, id: string | undefined) {
  return useQuery({
    queryKey: qk.detail(plural, id ?? ''),
    queryFn: () => getData<T>(`/api/${plural}/${id}`),
    enabled: !!id,
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}
export const useHarness = (id?: string) => useDetail<HarnessDetail>('harnesses', id);
export const useIdea = (id?: string) => useDetail<IdeaDetail>('ideas', id);
export const useResource = (id?: string) => useDetail<ResourceDetail>('resources', id);
export const useCollection = (id?: string) => useDetail<CollectionDetail>('collections', id);

export const useSearch = (q: string, limit = 5) =>
  useQuery({
    queryKey: qk.search(q, limit),
    queryFn: () => getData<SearchResults>('/api/search', { q, limit }),
    enabled: q.trim().length >= 2,
    placeholderData: keepPreviousData,
  });

export const useProfile = (username?: string) =>
  useQuery({ queryKey: qk.profile(username ?? ''), queryFn: () => getData<PublicProfile>(`/api/users/${username}`), enabled: !!username });

export const useContributions = (username: string, type: string, page: number) =>
  useQuery({
    queryKey: qk.contributions(username, type, page),
    queryFn: () => apiFetch<Paginated<unknown>>(`/api/users/${username}/contributions`, { query: { type, page } }),
    placeholderData: keepPreviousData,
  });

/* ── Feedback ─────────────────────────────────────────────────────────── */
export const useComments = (t: TargetType, id: string, sort: string) =>
  useQuery({
    queryKey: qk.comments(t, id, sort),
    queryFn: () => apiFetch<Paginated<Comment>>(`/api/${TARGET[t].plural}/${id}/comments`, { query: { sort } }),
  });

export function usePostComment(t: TargetType, id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { body: string; parent_id?: string }) =>
      apiFetch<{ data: Comment }>(`/api/${TARGET[t].plural}/${id}/comments`, { method: 'POST', body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['comments', t, id] });
      void qc.invalidateQueries({ queryKey: qk.detail(TARGET[t].plural, id) });
    },
  });
}

export const useSuggestions = (t: TargetType, id: string, filters: { kind?: string; sort?: string }) =>
  useQuery({
    queryKey: qk.suggestions(t, id, filters),
    queryFn: () => apiFetch<Paginated<Suggestion>>(`/api/${TARGET[t].plural}/${id}/suggestions`, { query: filters }),
  });

export function usePostSuggestion(t: TargetType, id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { kind: string; title: string; body: string; ai_assisted?: boolean }) =>
      apiFetch<{ data: Suggestion }>(`/api/${TARGET[t].plural}/${id}/suggestions`, { method: 'POST', body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['suggestions', t, id] });
      void qc.invalidateQueries({ queryKey: qk.detail(TARGET[t].plural, id) });
      toast.success('Suggestion posted');
    },
  });
}

export const useReviews = (harnessId: string, sort: string) =>
  useQuery({
    queryKey: qk.reviews(harnessId, sort),
    queryFn: () => apiFetch<Paginated<Review>>(`/api/harnesses/${harnessId}/reviews`, { query: { sort } }),
  });

/* ── Optimistic toggles (spec §7.4) ───────────────────────────────────── */
type Toggle = 'upvote' | 'interest' | 'bookmark';
type Countable = { id: string; counts: Record<string, number>; viewer: { has_voted: boolean; has_interest?: boolean; has_bookmarked: boolean } };

const FIELD: Record<Toggle, { flag: 'has_voted' | 'has_interest' | 'has_bookmarked'; count: string }> = {
  upvote: { flag: 'has_voted', count: 'votes' },
  interest: { flag: 'has_interest', count: 'interest' },
  bookmark: { flag: 'has_bookmarked', count: 'bookmarks' },
};

function patchItem<T extends Countable>(item: T, id: string, kind: Toggle, active: boolean, count?: number): T {
  if (item.id !== id) return item;
  const f = FIELD[kind];
  const was = !!item.viewer[f.flag];
  const c = count ?? (item.counts[f.count] ?? 0) + (active === was ? 0 : active ? 1 : -1);
  return { ...item, viewer: { ...item.viewer, [f.flag]: active }, counts: { ...item.counts, [f.count]: c } };
}

export function useToggle(t: TargetType, id: string, kind: Toggle) {
  const qc = useQueryClient();
  const plural = TARGET[t].plural;
  const detailKey = qk.detail(plural, id);
  const listKey: QueryKey = [plural, 'list'];

  const apply = (active: boolean, count?: number) => {
    qc.setQueryData<Countable>(detailKey, (d) => (d ? patchItem(d, id, kind, active, count) : d));
    qc.setQueriesData<Paginated<Countable>>({ queryKey: listKey }, (p) =>
      p ? { ...p, data: p.data.map((x) => patchItem(x, id, kind, active, count)) } : p,
    );
  };

  return useMutation({
    mutationFn: async (active: boolean) => {
      const path = kind === 'bookmark' ? `/api/bookmarks/${t}/${id}` : `/api/votes/${t}/${id}`;
      return apiFetch<{ data: { count: number; active: boolean } }>(path, {
        method: active ? 'PUT' : 'DELETE',
        query: kind === 'bookmark' ? undefined : { kind },
      });
    },
    onMutate: async (active) => {
      await qc.cancelQueries({ queryKey: detailKey });
      const prevDetail = qc.getQueryData(detailKey);
      const prevLists = qc.getQueriesData({ queryKey: listKey });
      apply(active);
      return { prevDetail, prevLists };
    },
    onError: (_e, _v, ctx) => {
      if (!ctx) return;
      qc.setQueryData(detailKey, ctx.prevDetail);
      ctx.prevLists.forEach(([k, v]) => qc.setQueryData(k, v));
    },
    onSuccess: (res, active) => {
      if (kind !== 'bookmark' && res?.data) apply(res.data.active, res.data.count);
      if (kind === 'bookmark') toast.success(active ? 'Saved to bookmarks' : 'Removed from bookmarks');
    },
  });
}
