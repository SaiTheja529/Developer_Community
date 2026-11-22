import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { apiFetch, getData } from './client';
import type { AIDraft, AIToday, Paginated } from './types';

export const draftKey = (id: string) => ['ai', 'draft', id] as const;
export const useDraft = (id: string | null | undefined) =>
  useQuery({ queryKey: draftKey(id ?? ''), queryFn: () => getData<AIDraft>(`/api/ai/drafts/${id}`), enabled: !!id, staleTime: 0 });

export const useDrafts = (filters: { task?: string; status?: string; page?: number }) =>
  useQuery({
    queryKey: ['ai', 'drafts', filters],
    queryFn: () => apiFetch<Paginated<AIDraft>>('/api/ai/drafts', { query: { ...filters, page_size: 20 } }),
    placeholderData: keepPreviousData,
  });

export const useAIStatus = () =>
  useQuery({ queryKey: ['ai', 'status'], queryFn: () => getData<{ enabled: boolean; model_label: string; reason?: string; today?: AIToday }>('/api/ai/status'), staleTime: 30_000 });
