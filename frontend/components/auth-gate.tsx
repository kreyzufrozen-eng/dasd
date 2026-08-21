'use client';

import * as React from 'react';
import { usePathname, useRouter } from 'next/navigation';

import { useAuth } from '@/lib/auth-context';
import { useActiveProfile } from '@/lib/profile-context';

const PUBLIC_PATHS = ['/login', '/register'];
// Legal/support pages: viewable with or without a session — unlike
// /login|/register, a logged-in user is never bounced away from these.
const ALWAYS_ACCESSIBLE_PATHS = ['/privacy', '/terms', '/cookies', '/delete-account', '/support'];
const ONBOARDING_PATH = '/onboarding';

// Wraps the app content: redirects to /login when there's no session,
// away from /login|/register back to the app once there is one, and into
// /onboarding when a logged-in user has zero SearchProfiles yet (an empty
// Dashboard would otherwise be the first thing they see — see
// IMPLEMENTATION_PLAN.md Этап 4). Never redirects AWAY from /onboarding
// just because profiles already exist — "+ Создать новый поиск" (Этап 9)
// reuses the same wizard for a user's second/third search.
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const { profiles, loading: profilesLoading } = useActiveProfile();
  const pathname = usePathname();
  const router = useRouter();
  const isPublicPath = PUBLIC_PATHS.includes(pathname ?? '');
  const isAlwaysAccessiblePath = ALWAYS_ACCESSIBLE_PATHS.includes(pathname ?? '');
  const isOnboardingPath = pathname === ONBOARDING_PATH;
  const loading = !isAlwaysAccessiblePath && (authLoading || (!!user && profilesLoading));
  const needsOnboarding = !!user && !profilesLoading && profiles.length === 0;

  React.useEffect(() => {
    if (loading || isAlwaysAccessiblePath) return;
    if (!user && !isPublicPath) {
      router.replace('/login');
    } else if (user && isPublicPath) {
      router.replace('/');
    } else if (needsOnboarding && !isOnboardingPath) {
      router.replace(ONBOARDING_PATH);
    }
  }, [loading, user, isPublicPath, isAlwaysAccessiblePath, needsOnboarding, isOnboardingPath, router]);

  if (isAlwaysAccessiblePath) {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center text-sm text-muted-foreground">
        Загрузка…
      </div>
    );
  }

  if (
    (!user && !isPublicPath) ||
    (user && isPublicPath) ||
    (needsOnboarding && !isOnboardingPath)
  ) {
    return null;
  }

  return <>{children}</>;
}
