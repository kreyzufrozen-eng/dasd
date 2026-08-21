'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';

import { ApiError, getProfileAnalytics, getSearchProfile } from '@/lib/api';
import { cn, formatBudget } from '@/lib/utils';
import type { AnalyticsPeriod, ProfileAnalytics, SearchProfileRead } from '@/lib/types';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { SimpleBarChart } from '@/components/simple-bar-chart';

const PERIODS: { value: AnalyticsPeriod; label: string }[] = [
  { value: 'today', label: 'Сегодня' },
  { value: '7d', label: '7 дней' },
  { value: '30d', label: '30 дней' },
  { value: 'all', label: 'Всё время' },
];

export default function SearchProfileAnalyticsPage() {
  const params = useParams<{ id: string }>();
  const profileId = Number(params.id);

  const [profile, setProfile] = React.useState<SearchProfileRead | null>(null);
  const [period, setPeriod] = React.useState<AnalyticsPeriod>('7d');
  const [data, setData] = React.useState<ProfileAnalytics | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!profileId) return;
    getSearchProfile(profileId).catch(() => undefined).then((p) => p && setProfile(p));
  }, [profileId]);

  React.useEffect(() => {
    if (!profileId) return;
    setLoading(true);
    setError(null);
    getProfileAnalytics(profileId, period)
      .then(setData)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить аналитику');
      })
      .finally(() => setLoading(false));
  }, [profileId, period]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            📊 Аналитика{profile ? `: ${profile.name}` : ''}
          </h1>
          <p className="text-sm text-muted-foreground">Воронка и статистика этого поиска</p>
        </div>
        <Link
          href={`/searches/${profileId}`}
          className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
        >
          ← К настройкам поиска
        </Link>
      </div>

      <div className="flex flex-wrap gap-1">
        {PERIODS.map((p) => (
          <Button
            key={p.value}
            size="sm"
            variant={period === p.value ? 'default' : 'outline'}
            onClick={() => setPeriod(p.value)}
          >
            {p.label}
          </Button>
        ))}
      </div>

      {error && (
        <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {loading && !data ? (
        <p className="text-sm text-muted-foreground">Загрузка…</p>
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <FunnelCard label="Кандидаты" value={data.funnel.candidates} hint="прошли фильтр ключевых слов и дошли до AI" />
            <FunnelCard label="Лиды" value={data.funnel.leads} hint="AI признал релевантными" />
            <FunnelCard label="🔥 Горячие лиды" value={data.funnel.hot_leads} hint="выше порога уведомлений" />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-foreground">
                  Средний Match Score
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold">{data.avg_match_score}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-foreground">
                  Средний бюджет
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold">
                  {data.avg_budget != null
                    ? formatBudget(data.avg_budget, data.avg_budget, data.budget_currency)
                    : '—'}
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold text-foreground">
                Лиды по дням
              </CardTitle>
            </CardHeader>
            <CardContent>
              <SimpleBarChart data={data.leads_by_day} />
            </CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-foreground">
                  Лучшие источники
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.top_sources.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Нет данных за период</p>
                ) : (
                  <ul className="space-y-1.5">
                    {data.top_sources.map((s) => (
                      <li key={s.source_id} className="flex items-center justify-between text-sm">
                        <span className="truncate">{s.source_name}</span>
                        <span className="font-medium text-foreground">{s.lead_count}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-foreground">
                  Лучшие ниши
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.top_niches.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Нет данных за период</p>
                ) : (
                  <ul className="space-y-1.5">
                    {data.top_niches.map((n) => (
                      <li key={n.niche} className="flex items-center justify-between text-sm">
                        <span className="truncate">{n.niche}</span>
                        <span className="font-medium text-foreground">{n.lead_count}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}

function FunnelCard({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-semibold text-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold">{value}</p>
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  );
}
