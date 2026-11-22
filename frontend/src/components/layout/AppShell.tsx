import { Suspense, useEffect, useState } from 'react';
import { Link, NavLink, Outlet, ScrollRestoration, useLocation, useNavigate } from 'react-router';
import * as Dropdown from '@radix-ui/react-dropdown-menu';
import * as Dialog from '@radix-ui/react-dialog';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Bot, BookOpen, Bookmark, FileText, Home, Lightbulb, LogOut, MailWarning, Moon, Plus, Search, Settings, Shield, Sun, User, Users, Wrench } from 'lucide-react';
import { useAuth } from '@/features/auth/AuthProvider';
import { useTheme } from '@/hooks/useTheme';
import { MODULES, type ModuleKey } from '@/lib/modules';
import { cn } from '@/lib/cn';
import { Avatar } from '@/components/common/Meta';
import { CommandPalette } from '@/features/search/CommandPalette';
import { NotificationBell } from '@/features/notifications/Notifications';
import { AskAIPanel } from '@/features/ai/AskAIPanel';
import { useAI } from '@/features/ai/store';
import { getData } from '@/lib/api/client';
import { qk } from '@/lib/queryKeys';
import { resendVerification } from '@/features/auth/resend';
import { Button } from '@/components/common/Button';
import { Skeleton } from '@/components/common/States';

export function Logo() {
  return (
    <Link to="/" className="inline-flex items-center gap-2 font-semibold tracking-tight" aria-label="DevCommons home">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
        <path d="M16 3 29 10.5v11L16 29 3 21.5v-11z" fill="var(--surface)" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
        <path d="M16 3v26M3 10.5l13 7.5 13-7.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
        <rect x="18.5" y="15" width="4" height="8" fill="var(--harness)" />
        <circle cx="10" cy="17" r="2.4" fill="var(--idea)" />
      </svg>
      <span>DevCommons</span>
    </Link>
  );
}

const NAV: { key: ModuleKey; to: string; match: string[] }[] = [
  { key: 'harness', to: '/harnesses', match: ['/harnesses'] },
  { key: 'idea', to: '/ideas', match: ['/ideas'] },
  { key: 'knowledge', to: '/resources', match: ['/resources', '/collections'] },
  { key: 'ai', to: '/ai', match: ['/ai'] },
];

function useActiveModule(): ModuleKey | null {
  const { pathname } = useLocation();
  return NAV.find((n) => n.match.some((m) => pathname.startsWith(m)))?.key ?? null;
}

function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggle } = useTheme();
  return (
    <button type="button" onClick={toggle} className={cn('grid size-9 cursor-pointer place-items-center rounded-[6px] hover:bg-surface-2', className)} aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
      {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  );
}

const menuItem = 'flex cursor-pointer items-center gap-2 rounded-[6px] px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-surface-2';
const menuContent = 'z-50 min-w-[220px] rounded-[10px] border border-border bg-surface p-1 shadow-[var(--shadow-dialog)]';

function NewMenu() {
  const navigate = useNavigate();
  const items = [
    ['Submit a harness', '/harnesses/new'], ['Share a project idea', '/ideas/new'], ['Add a resource', '/resources/new'],
    ['Create a collection', '/collections/new'], ['Generate with AI', '/ai/generate'],
  ] as const;
  return (
    <Dropdown.Root>
      <Dropdown.Trigger asChild>
        <Button variant="primary" size="md"><Plus size={15} aria-hidden /> New</Button>
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content align="end" sideOffset={6} className={menuContent}>
          {items.map(([label, to]) => (
            <Dropdown.Item key={to} className={menuItem} onSelect={() => navigate(to)}>{label}</Dropdown.Item>
          ))}
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

function UserMenu() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const { theme, toggle } = useTheme();
  if (!user) return null;
  return (
    <Dropdown.Root>
      <Dropdown.Trigger className="grid size-9 cursor-pointer place-items-center rounded-full" aria-label="Account menu">
        <Avatar user={user} size={30} />
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content align="end" sideOffset={6} className={menuContent}>
          <div className="px-2.5 py-2">
            <p className="text-sm font-medium">{user.display_name}</p>
            <p className="font-mono text-xs text-muted">@{user.username}</p>
          </div>
          <Dropdown.Separator className="my-1 h-px bg-border" />
          <Dropdown.Item className={menuItem} onSelect={() => navigate(`/u/${user.username}`)}><User size={15} /> Profile</Dropdown.Item>
          <Dropdown.Item className={menuItem} onSelect={() => navigate('/me/bookmarks')}><Bookmark size={15} /> Bookmarks</Dropdown.Item>
          <Dropdown.Item className={menuItem} onSelect={() => navigate('/me/collaborations')}><Users size={15} /> Collaborations</Dropdown.Item>
          <Dropdown.Item className={menuItem} onSelect={() => navigate('/ai/drafts')}><FileText size={15} /> AI drafts</Dropdown.Item>
          <Dropdown.Item className={menuItem} onSelect={() => navigate('/settings/profile')}><Settings size={15} /> Settings</Dropdown.Item>
          {(user.role === 'moderator' || user.role === 'admin') && <Dropdown.Item className={menuItem} onSelect={() => navigate(user.role === 'admin' ? '/admin' : '/admin/reports')}><Shield size={15} /> Admin</Dropdown.Item>}
          <Dropdown.Item className={menuItem} onSelect={(e) => { e.preventDefault(); toggle(); }}>
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />} {theme === 'dark' ? 'Light theme' : 'Dark theme'}
          </Dropdown.Item>
          <Dropdown.Separator className="my-1 h-px bg-border" />
          <Dropdown.Item className={menuItem} onSelect={async () => { await signOut(); navigate('/'); toast('Signed out'); }}><LogOut size={15} /> Sign out</Dropdown.Item>
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

function TopNav({ onSearch }: { onSearch: () => void }) {
  const active = useActiveModule();
  const { status } = useAuth();
  const loc = useLocation();
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-[color-mix(in_srgb,var(--bg)_88%,transparent)] backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-4 px-4 md:px-8">
        <Logo />
        <nav aria-label="Modules" className="hidden items-center gap-1 md:flex">
          {NAV.map((n) => {
            const m = MODULES[n.key];
            const on = active === n.key;
            return (
              <NavLink key={n.key} to={n.to} className={cn('relative px-2.5 py-1.5 text-sm font-medium', on ? 'text-text' : 'text-muted hover:text-text')} aria-current={on ? 'page' : undefined}>
                {m.name}
                <span className="absolute inset-x-2.5 -bottom-[11px] h-[2px] rounded-full transition-opacity" style={{ background: m.color, opacity: on ? 1 : 0 }} aria-hidden />
              </NavLink>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-1.5">
          <button type="button" onClick={onSearch} className="hidden h-9 w-56 cursor-pointer items-center gap-2 rounded-[6px] border border-border bg-surface px-2.5 text-sm text-muted hover:border-muted lg:flex">
            <Search size={15} aria-hidden /> Search
            <kbd className="ml-auto rounded border border-border px-1 font-mono text-[11px]">⌘K</kbd>
          </button>
          <button type="button" onClick={onSearch} className="grid size-9 cursor-pointer place-items-center rounded-[6px] hover:bg-surface-2 lg:hidden" aria-label="Search">
            <Search size={17} />
          </button>
          {status === 'signed_in' ? (
            <>
              <span className="hidden md:block"><NewMenu /></span>
              <NotificationBell />
              <UserMenu />
            </>
          ) : status === 'signed_out' ? (
            <>
              <ThemeToggle />
              <Link to={`/sign-in?next=${encodeURIComponent(loc.pathname)}`} className="hidden h-9 items-center px-2.5 text-sm font-medium hover:underline sm:inline-flex">Sign in</Link>
              <Link to="/sign-up" className="inline-flex h-9 items-center rounded-[6px] bg-text px-3.5 text-sm font-medium text-bg">Join</Link>
            </>
          ) : (
            <Skeleton className="h-9 w-24" />
          )}
        </div>
      </div>
    </header>
  );
}

function MobileNav() {
  const active = useActiveModule();
  const { pathname } = useLocation();
  const items = [
    { to: '/', label: 'Home', icon: Home, on: pathname === '/' },
    { to: '/harnesses', label: 'Harnesses', icon: Wrench, on: active === 'harness', color: MODULES.harness.color },
    { to: '/ideas', label: 'Ideas', icon: Lightbulb, on: active === 'idea', color: MODULES.idea.color },
    { to: '/resources', label: 'Knowledge', icon: BookOpen, on: active === 'knowledge', color: MODULES.knowledge.color },
    { to: '/ai', label: 'AI', icon: Bot, on: active === 'ai', color: MODULES.ai.color },
  ];
  return (
    <nav aria-label="Primary" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-border bg-surface pb-[env(safe-area-inset-bottom)] md:hidden">
      {items.map(({ to, label, icon: Icon, on, color }) => (
        <Link key={to} to={to} aria-current={on ? 'page' : undefined} className={cn('flex min-h-[52px] flex-col items-center justify-center gap-0.5 text-[11px]', on ? 'font-medium text-text' : 'text-muted')}>
          <Icon size={19} style={on && color ? { color } : undefined} aria-hidden />
          {label}
        </Link>
      ))}
    </nav>
  );
}

function Footer() {
  return (
    <footer className="mt-16 border-t border-border pb-20 md:pb-0">
      <div className="mx-auto flex max-w-[1200px] flex-col gap-3 px-4 py-8 text-sm text-muted md:flex-row md:items-center md:justify-between md:px-8">
        <nav aria-label="Footer" className="flex flex-wrap gap-x-4 gap-y-1">
          <Link to="/about" className="hover:text-text">About</Link>
          <Link to="/guidelines" className="hover:text-text">Community guidelines</Link>
          <Link to="/privacy" className="hover:text-text">Privacy</Link>
          <Link to="/terms" className="hover:text-text">Terms</Link>
        </nav>
        <p className="font-mono text-xs">Community content is licensed CC BY 4.0 unless noted.</p>
      </div>
    </footer>
  );
}

function Banners() {
  const { user } = useAuth();
  const { data: ai } = useQuery({ queryKey: qk.aiStatus, queryFn: () => getData<{ enabled: boolean }>('/api/ai/status'), staleTime: 300_000 });
  const [sent, setSent] = useState(false);
  return (
    <>
      {user?.status === 'suspended' && (
        <div role="status" className="border-b border-danger bg-danger-soft px-4 py-2 text-center text-sm text-danger">Your account is suspended. You can read, but you can't post right now.</div>
      )}
      {user && !user.email_verified && (
        <div role="status" className="flex flex-wrap items-center justify-center gap-3 border-b border-warning bg-warning-soft px-4 py-2 text-sm">
          <MailWarning size={15} className="text-warning" aria-hidden /> Verify your email to start posting.
          <button
            type="button"
            disabled={sent}
            className="cursor-pointer font-medium underline disabled:no-underline disabled:opacity-60"
            onClick={async () => {
              const r = await resendVerification();
              if (r.ok) setSent(true);
              (r.ok ? toast.success : toast.error)(r.message);
            }}
          >
            {sent ? 'Sent' : 'Resend email'}
          </button>
        </div>
      )}
      {ai && !ai.enabled && (
        <div role="status" className="border-b border-ai bg-ai-soft px-4 py-2 text-center text-sm text-ai">AI is temporarily unavailable. Everything else works as usual.</div>
      )}
    </>
  );
}

function VerifyEmailDialog() {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  useEffect(() => {
    const f = () => setOpen(true);
    window.addEventListener('dc:verify-email', f);
    return () => window.removeEventListener('dc:verify-email', f);
  }, []);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(92vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-[14px] border border-border bg-surface p-6 shadow-[var(--shadow-dialog)]">
          <Dialog.Title className="text-lg font-semibold">Check your inbox</Dialog.Title>
          <Dialog.Description className="mt-2 text-sm text-muted">
            Verify your email before posting. We sent a link to {user?.email ?? 'your address'}.
          </Dialog.Description>
          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild><Button>Close</Button></Dialog.Close>
            <Button variant="primary" onClick={async () => { const r = await resendVerification(); (r.ok ? toast.success : toast.error)(r.message); if (r.ok) setOpen(false); }}>Resend email</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function SessionEndedListener() {
  const navigate = useNavigate();
  const loc = useLocation();
  useEffect(() => {
    const f = () => {
      toast('Your session ended. Please sign in again.');
      navigate(`/sign-in?next=${encodeURIComponent(loc.pathname)}`);
    };
    window.addEventListener('dc:session-ended', f);
    return () => window.removeEventListener('dc:session-ended', f);
  }, [navigate, loc.pathname]);
  return null;
}

export function AppShell() {
  const [searchOpen, setSearchOpen] = useState(false);
  const isChat = useLocation().pathname.startsWith('/ai');
  const panelOpen = useAI((s) => s.panel.open);
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen((o) => !o);
      }
    };
    window.addEventListener('keydown', f);
    return () => window.removeEventListener('keydown', f);
  }, []);
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only z-50 rounded bg-text px-3 py-2 text-bg focus:not-sr-only focus:fixed focus:top-2 focus:left-2">Skip to content</a>
      <TopNav onSearch={() => setSearchOpen(true)} />
      <Banners />
      <main id="main" className={cn('flex-1 transition-[padding] duration-200', panelOpen && 'lg:pr-[420px]')} tabIndex={-1}>
        <Suspense fallback={<div className="mx-auto max-w-[1200px] px-4 py-10 md:px-8"><Skeleton className="h-8 w-1/3" /><Skeleton className="mt-4 h-4 w-2/3" /></div>}>
          <Outlet />
        </Suspense>
      </main>
      {!isChat && <Footer />}
      <MobileNav />
      <CommandPalette open={searchOpen} onOpenChange={setSearchOpen} />
      <AskAIPanel />
      <VerifyEmailDialog />
      <SessionEndedListener />
      <ScrollRestoration />
    </div>
  );
}
