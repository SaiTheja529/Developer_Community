import { useQuery } from '@tanstack/react-query';
import { getData } from '@/lib/api/client';
import type { AppConfig } from '@/lib/api/types';
import { qk } from '@/lib/queryKeys';

export const configQuery = { queryKey: qk.config, queryFn: () => getData<AppConfig>('/api/meta/config'), staleTime: 3_600_000 };
export const useConfig = () => useQuery(configQuery);
