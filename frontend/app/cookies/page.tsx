'use client';

import * as React from 'react';

import { acceptAll, getStoredConsent, rejectNonEssential, storeConsent } from '@/lib/cookie-consent';
import { LegalDocumentPage } from '@/components/legal-document-page';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function CookiesPage() {
  const [analytics, setAnalytics] = React.useState(false);
  const [marketing, setMarketing] = React.useState(false);
  const [saved, setSaved] = React.useState(false);

  React.useEffect(() => {
    const stored = getStoredConsent();
    if (stored) {
      setAnalytics(stored.analytics);
      setMarketing(stored.marketing);
    }
  }, []);

  return (
    <div className="space-y-6">
      <Card className="mx-auto max-w-2xl">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">
            Настройки cookies
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="flex items-center justify-between text-sm">
            <span>Необходимые (вход в аккаунт) — всегда включены</span>
            <input type="checkbox" checked disabled className="h-4 w-4" />
          </label>
          <label className="flex items-center justify-between text-sm">
            <span>Аналитика</span>
            <input
              type="checkbox"
              checked={analytics}
              onChange={(e) => setAnalytics(e.target.checked)}
              className="h-4 w-4"
            />
          </label>
          <label className="flex items-center justify-between text-sm">
            <span>Маркетинг</span>
            <input
              type="checkbox"
              checked={marketing}
              onChange={(e) => setMarketing(e.target.checked)}
              className="h-4 w-4"
            />
          </label>
          <p className="text-xs text-muted-foreground">
            Сейчас ReadHunter устанавливает только один технически необходимый cookie для входа в
            аккаунт — аналитические и маркетинговые cookies пока не используются. Этот переключатель
            заранее готов к моменту, когда они появятся.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              size="sm"
              onClick={() => {
                storeConsent({ analytics, marketing });
                setSaved(true);
              }}
            >
              {saved ? 'Сохранено' : 'Сохранить выбор'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                const c = acceptAll();
                setAnalytics(c.analytics);
                setMarketing(c.marketing);
                setSaved(true);
              }}
            >
              Принять все
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                const c = rejectNonEssential();
                setAnalytics(c.analytics);
                setMarketing(c.marketing);
                setSaved(true);
              }}
            >
              Только необходимые
            </Button>
          </div>
        </CardContent>
      </Card>

      <LegalDocumentPage type="cookie_policy" fallbackTitle="Политика использования cookies" />
    </div>
  );
}
