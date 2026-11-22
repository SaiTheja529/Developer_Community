import { lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router';
import { AppShell } from '@/components/layout/AppShell';
import { AuthCallbackPage, AuthLayout, CheckEmailPage, ForgotPasswordPage, RequireAuth, ResetPasswordPage, SignInPage, SignUpPage, VerifyEmailPage } from '@/features/auth/AuthPages';
import { NotFoundPage, StaticPage } from '@/features/static/StaticPages';

const HomePage = lazy(() => import('@/features/home/HomePage'));
const SearchPage = lazy(() => import('@/features/search/SearchPage'));
const HarnessListPage = lazy(() => import('@/features/harnesses/HarnessListPage'));
const HarnessDetailPage = lazy(() => import('@/features/harnesses/HarnessDetailPage'));
const HarnessFormPage = lazy(() => import('@/features/harnesses/HarnessFormPage'));
const IdeaListPage = lazy(() => import('@/features/ideas/IdeaListPage'));
const IdeaDetailPage = lazy(() => import('@/features/ideas/IdeaDetailPage'));
const IdeaFormPage = lazy(() => import('@/features/ideas/IdeaFormPage'));
const ResourceListPage = lazy(() => import('@/features/resources/ResourceListPage'));
const ResourceDetailPage = lazy(() => import('@/features/resources/ResourceDetailPage'));
const ResourceFormPage = lazy(() => import('@/features/resources/ResourceFormPage'));
const CollectionListPage = lazy(() => import('@/features/collections/CollectionListPage'));
const CollectionDetailPage = lazy(() => import('@/features/collections/CollectionDetailPage'));
const CollectionFormPage = lazy(() => import('@/features/collections/CollectionFormPage'));
const ChatPage = lazy(() => import('@/features/ai/ChatPage'));
const ProfilePage = lazy(() => import('@/features/users/ProfilePage'));
const BookmarksPage = lazy(() => import('@/features/bookmarks/BookmarksPage'));
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const named = <T,>(loader: () => Promise<T>, name: keyof T) =>
  lazy(() => loader().then((m) => ({ default: m[name] as unknown as React.ComponentType })));
const GeneratePickerPage = named(() => import('@/features/ai/generate/GeneratePages'), 'GeneratePickerPage');
const GenerateTaskPage = named(() => import('@/features/ai/generate/GeneratePages'), 'GenerateTaskPage');
const DraftsListPage = named(() => import('@/features/ai/generate/DraftPages'), 'DraftsListPage');
const DraftReviewPage = named(() => import('@/features/ai/generate/DraftPages'), 'DraftReviewPage');
const CollaborationsPage = named(() => import('@/features/collaborations/CollaborationPages'), 'CollaborationsPage');
const IdeaRequestsPage = named(() => import('@/features/collaborations/CollaborationPages'), 'IdeaRequestsPage');
const NotificationsPage = named(() => import('@/features/notifications/Notifications'), 'NotificationsPage');
const SettingsLayout = named(() => import('@/features/settings/SettingsPages'), 'SettingsLayout');
const ProfileSettingsPage = named(() => import('@/features/settings/SettingsPages'), 'ProfileSettingsPage');
const PrivacySettingsPage = named(() => import('@/features/settings/SettingsPages'), 'PrivacySettingsPage');
const AISettingsPage = named(() => import('@/features/settings/SettingsPages'), 'AISettingsPage');
const AccountSettingsPage = named(() => import('@/features/settings/SettingsPages'), 'AccountSettingsPage');
const AdminGate = named(() => import('@/features/admin/AdminPages'), 'AdminLayout');
const AdminOverviewPage = named(() => import('@/features/admin/AdminPages'), 'AdminOverviewPage');
const AdminReportsPage = named(() => import('@/features/admin/AdminPages'), 'AdminReportsPage');
const AdminUsersPage = named(() => import('@/features/admin/AdminPages'), 'AdminUsersPage');
const AdminDomainsPage = named(() => import('@/features/admin/AdminPages'), 'AdminDomainsPage');
const AdminLogPage = named(() => import('@/features/admin/AdminPages'), 'AdminLogPage');
const RequireRole = lazy(() => import('@/features/admin/AdminPages').then((m) => ({ default: m.RequireRole })));

const auth = (el: React.ReactNode) => <RequireAuth>{el}</RequireAuth>;

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    errorElement: <NotFoundPage />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/search', element: <SearchPage /> },
      { path: '/harnesses', element: <HarnessListPage /> },
      { path: '/harnesses/new', element: auth(<HarnessFormPage />) },
      { path: '/harnesses/:id/edit', element: auth(<HarnessFormPage />) },
      { path: '/harnesses/:id/:slug?', element: <HarnessDetailPage /> },
      { path: '/ideas', element: <IdeaListPage /> },
      { path: '/ideas/new', element: auth(<IdeaFormPage />) },
      { path: '/ideas/:id/edit', element: auth(<IdeaFormPage />) },
      { path: '/ideas/:id/requests', element: auth(<IdeaRequestsPage />) },
      { path: '/ideas/:id/:slug?', element: <IdeaDetailPage /> },
      { path: '/resources', element: <ResourceListPage /> },
      { path: '/resources/new', element: auth(<ResourceFormPage />) },
      { path: '/resources/:id/edit', element: auth(<ResourceFormPage />) },
      { path: '/resources/:id', element: <ResourceDetailPage /> },
      { path: '/collections', element: <CollectionListPage /> },
      { path: '/collections/new', element: auth(<CollectionFormPage />) },
      { path: '/collections/:id/edit', element: auth(<CollectionFormPage />) },
      { path: '/collections/:id/:slug?', element: <CollectionDetailPage /> },
      { path: '/ai', element: auth(<ChatPage />) },
      { path: '/ai/c/:conversationId', element: auth(<ChatPage />) },
      { path: '/ai/generate', element: auth(<GeneratePickerPage />) },
      { path: '/ai/generate/:task', element: auth(<GenerateTaskPage />) },
      { path: '/ai/drafts', element: auth(<DraftsListPage />) },
      { path: '/ai/drafts/:id', element: auth(<DraftReviewPage />) },
      { path: '/u/:username', element: <ProfilePage /> },
      { path: '/me/bookmarks', element: auth(<BookmarksPage />) },
      { path: '/me/collaborations', element: auth(<CollaborationsPage />) },
      { path: '/notifications', element: auth(<NotificationsPage />) },
      {
        path: '/settings',
        element: auth(<SettingsLayout />),
        children: [
          { index: true, element: <Navigate to="/settings/profile" replace /> },
          { path: 'profile', element: <ProfileSettingsPage /> },
          { path: 'privacy', element: <PrivacySettingsPage /> },
          { path: 'ai', element: <AISettingsPage /> },
          { path: 'account', element: <AccountSettingsPage /> },
        ],
      },
      {
        path: '/admin',
        element: auth(<RequireRole role="moderator"><AdminGate /></RequireRole>),
        children: [
          { index: true, element: <AdminOverviewPage /> },
          { path: 'reports', element: <AdminReportsPage /> },
          { path: 'users', element: <AdminUsersPage /> },
          { path: 'trusted-domains', element: <AdminDomainsPage /> },
          { path: 'log', element: <AdminLogPage /> },
        ],
      },
      { path: '/about', element: <StaticPage page="about" /> },
      { path: '/guidelines', element: <StaticPage page="guidelines" /> },
      { path: '/privacy', element: <StaticPage page="privacy" /> },
      { path: '/terms', element: <StaticPage page="terms" /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
  {
    element: <AuthLayout />,
    children: [
      { path: '/sign-in', element: <SignInPage /> },
      { path: '/sign-up', element: <SignUpPage /> },
      { path: '/auth/callback', element: <AuthCallbackPage /> },
      { path: '/check-email', element: <CheckEmailPage /> },
      { path: '/verify-email', element: <VerifyEmailPage /> },
      { path: '/forgot-password', element: <ForgotPasswordPage /> },
      { path: '/reset-password', element: <ResetPasswordPage /> },
    ],
  },
]);
