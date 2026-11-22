import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router';
import { Toaster } from 'sonner';
import { queryClient } from '@/lib/queryClient';
import { configQuery } from '@/hooks/useConfig';
import { AuthProvider } from '@/features/auth/AuthProvider';
import { router } from './router';
import './styles/globals.css';

void queryClient.prefetchQuery(configQuery);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
        <Toaster position="bottom-center" toastOptions={{ className: 'font-sans', style: { background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)' } }} />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
