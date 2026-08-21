'use client';

import * as React from 'react';

import { getSearchProfiles } from './api';
import { useAuth } from './auth-context';
import type { SearchProfileRead } from './types';

const ACTIVE_PROFILE_STORAGE_KEY = 'readhunter_active_profile_id';

interface ActiveProfileContextValue {
  profiles: SearchProfileRead[];
  activeProfile: SearchProfileRead | null;
  activeProfileId: number | null;
  setActiveProfileId: (id: number) => void;
  loading: boolean;
  refresh: () => Promise<void>;
}

const ActiveProfileContext = React.createContext<ActiveProfileContextValue | null>(null);

export function ActiveProfileProvider({ children }: { children: React.ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const [profiles, setProfiles] = React.useState<SearchProfileRead[]>([]);
  const [activeProfileId, setActiveProfileIdState] = React.useState<number | null>(null);
  const [loading, setLoading] = React.useState(true);

  const fetchProfiles = React.useCallback(async () => {
    const data = await getSearchProfiles();
    setProfiles(data);

    setActiveProfileIdState((current) => {
      if (current && data.some((p) => p.id === current)) return current;
      const stored = Number(localStorage.getItem(ACTIVE_PROFILE_STORAGE_KEY));
      if (stored && data.some((p) => p.id === stored)) return stored;
      return data[0]?.id ?? null;
    });
  }, []);

  React.useEffect(() => {
    // Wait for AuthProvider to resolve first. Without this guard, the
    // render right after `user` flips from null -> real user (but before
    // this effect's fetch has run) would still be holding last render's
    // `profiles: []` / `loading: false` from the "no user yet" branch
    // below — AuthGate reads exactly that stale combination as "logged
    // in with zero profiles" and bounces straight into /onboarding, even
    // for a user who has profiles. Staying loading=true through the
    // entire auth-resolution phase closes that window.
    if (authLoading) return;

    if (!user) {
      setProfiles([]);
      setActiveProfileIdState(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchProfiles()
      .catch(() => {
        // Non-fatal — pages relying on activeProfile handle the null case
        // as an empty state, same as "no leads found".
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, authLoading, fetchProfiles]);

  function setActiveProfileId(id: number) {
    setActiveProfileIdState(id);
    localStorage.setItem(ACTIVE_PROFILE_STORAGE_KEY, String(id));
  }

  const activeProfile = profiles.find((p) => p.id === activeProfileId) ?? null;

  const value = React.useMemo(
    () => ({
      profiles,
      activeProfile,
      activeProfileId,
      setActiveProfileId,
      loading,
      refresh: fetchProfiles,
    }),
    [profiles, activeProfile, activeProfileId, loading, fetchProfiles]
  );

  return (
    <ActiveProfileContext.Provider value={value}>{children}</ActiveProfileContext.Provider>
  );
}

export function useActiveProfile(): ActiveProfileContextValue {
  const ctx = React.useContext(ActiveProfileContext);
  if (!ctx) throw new Error('useActiveProfile must be used within ActiveProfileProvider');
  return ctx;
}
