'use client';

import * as React from 'react';
import Link from 'next/link';

import { acceptAll, getStoredConsent, rejectNonEssential, storeConsent } from '@/lib/cookie-consent';
import { Button } from '@/components/ui/button';

export function CookieConsentBanner() {
  const [visible, setVisible] = React.useState(false);
  const [customizing, setCustomizing] = React.useState(false);
  const [analytics, setAnalytics] = React.useState(false);
  const [marketing, setMarketing] = React.useState(false);

  React.useEffect(() => {
    setVisible(getStoredConsent() === null);
  }, []);

  if (!visible) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 border-t border-border bg-card p-4 shadow-lg">
      <div className="container flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Мы используем только технически необходимые cookies для входа в аккаунт. Подробнее в{' '}
          <Link href="/cookies" className="text-primary hover:underline">
            политике cookies
          </Link>
          .
        </p>

        {!customizing ? (
          <div className="flex shrink-0 gap-2">
            <Button size="sm" variant="outline" onClick={() => setCustomizing(true)}>
              Настроить
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                rejectNonEssential();
                setVisible(false);
              }}
            >
              Только необходимые
            </Button>
            <Button
              size="sm"
              onClick={() => {
                acceptAll();
                setVisible(false);
              }}
            >
              Принять все
            </Button>
          </div>
        ) : (
          <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center">
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <input type="checkbox" checked disabled className="h-3.5 w-3.5" />
              Необходимые
            </label>
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={analytics}
                onChange={(e) => setAnalytics(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              Аналитика
            </label>
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={marketing}
                onChange={(e) => setMarketing(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              Маркетинг
            </label>
            <Button
              size="sm"
              onClick={() => {
                storeConsent({ analytics, marketing });
                setVisible(false);
              }}
            >
              Сохранить
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
