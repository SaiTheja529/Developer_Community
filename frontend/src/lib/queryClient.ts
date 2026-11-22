import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ApiError } from './api/client';

function handleGlobalError(err: unknown) {
  if (!(err instanceof ApiError)) return;
  switch (err.code) {
    case 'forbidden':
      toast.error("You don't have permission to do that.");
      break;
    case 'rate_limited':
      toast.error(`Slow down a little. Try again in ${err.retryAfter ?? 30} seconds.`);
      break;
    case 'email_not_verified':
      window.dispatchEvent(new CustomEvent('dc:verify-email'));
      break;
    case 'unauthenticated':
    case 'token_expired':
    case 'session_revoked':
      window.dispatchEvent(new CustomEvent('dc:session-ended'));
      break;
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleGlobalError }),
  mutationCache: new MutationCache({ onError: handleGlobalError }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (count, err) => {
        if (err instanceof ApiError && err.status < 500) return false;
        return count < 2;
      },
    },
  },
});
