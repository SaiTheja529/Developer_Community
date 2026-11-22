import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { MeProfile } from '@/lib/api/types';
import { ApiError, toApiError } from '@/lib/api/client';
import { qk } from '@/lib/queryKeys';
import { authFetch, broadcastSignedIn, clearSession, onSessionUser, refreshSession, setSession } from './session';

type AuthStatus = 'loading' | 'signed_out' | 'signed_in';
interface AuthContextValue {
  status: AuthStatus;
  user: MeProfile | null;
  isVerified: boolean;
  signIn(email: string, password: string): Promise<void>;
  signUp(input: { email: string; password: string; username: string; display_name: string }): Promise<void>;
  signOut(): Promise<void>;
}

const Ctx = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<MeProfile | null>(null);

  useEffect(() => {
    const off = onSessionUser((u) => {
      setUser(u);
      setStatus(u ? 'signed_in' : 'signed_out');
      if (u) qc.setQueryData(qk.me, u);
      else qc.clear();
    });
    void refreshSession().then((ok) => {
      if (!ok) setStatus('signed_out');
    });
    return () => void off();
  }, [qc]);

  const establish = useCallback(async (res: Response) => {
    if (!res.ok) throw await toApiError(res);
    const { data } = await res.json();
    setSession(data.access_token, data.expires_in, data.user);
    broadcastSignedIn();
    await qc.invalidateQueries();
  }, [qc]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      isVerified: !!user?.email_verified,
      signIn: async (email, password) => {
        await establish(await authFetch('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }));
      },
      signUp: async (input) => {
        await establish(await authFetch('/api/auth/register', { method: 'POST', body: JSON.stringify(input) }));
      },
      signOut: async () => {
        await authFetch('/api/auth/logout', { method: 'POST' }).catch(() => undefined);
        clearSession();
        qc.clear();
      },
    }),
    [status, user, establish, qc],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth outside AuthProvider');
  return v;
}

export { ApiError };
