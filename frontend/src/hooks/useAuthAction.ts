import { useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { useAuth } from '@/features/auth/AuthProvider';

/** Runs an action, or prompts sign-in / email verification first (spec §8.4). */
export function useAuthAction() {
  const { status, isVerified } = useAuth();
  const navigate = useNavigate();
  const loc = useLocation();
  return useCallback(
    (fn: () => void, { requireVerified = true } = {}) => {
      if (status !== 'signed_in') {
        navigate(`/sign-in?next=${encodeURIComponent(loc.pathname + loc.search)}`);
        return;
      }
      if (requireVerified && !isVerified) {
        window.dispatchEvent(new CustomEvent('dc:verify-email'));
        return;
      }
      fn();
    },
    [status, isVerified, navigate, loc],
  );
}
