'use client';

// Cookie consent, categorized per the spec's necessary/analytics/marketing
// split. Honest state of this app today: the ONLY cookie it ever sets is
// the httpOnly `access_token` session cookie (strictly necessary — you
// can't stay logged in without it). There is no analytics or marketing
// script anywhere in the codebase yet, so those two categories are real
// architecture prep for when/if such a script gets added, not cookies
// that actually exist right now. Recording the choice is still useful:
// it's what a future analytics/marketing integration must check before
// setting anything non-essential.
export type CookieCategory = 'necessary' | 'analytics' | 'marketing';

export interface CookieConsent {
  necessary: true; // always on, not a real choice
  analytics: boolean;
  marketing: boolean;
  decidedAt: string;
}

const STORAGE_KEY = 'readhunter_cookie_consent';

export function getStoredConsent(): CookieConsent | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as CookieConsent;
  } catch {
    return null;
  }
}

export function storeConsent(consent: Omit<CookieConsent, 'necessary' | 'decidedAt'>): CookieConsent {
  const full: CookieConsent = { necessary: true, ...consent, decidedAt: new Date().toISOString() };
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(full));
  }
  return full;
}

export function acceptAll(): CookieConsent {
  return storeConsent({ analytics: true, marketing: true });
}

export function rejectNonEssential(): CookieConsent {
  return storeConsent({ analytics: false, marketing: false });
}
