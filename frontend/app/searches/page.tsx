'use client';

import * as React from 'react';
import Link from 'next/link';
import { Plus } from 'lucide-react';

import {
  ApiError,
  getAnalyticsOverview,
  getProfileKeywords,
  getProfileSources,
} from '@/lib/api';
import { useActiveProfile } from '@/lib/profile-context';
import type { SearchProfileRead } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface ProfileStats {
  sourceCount: number;
  keywordCount: number;
  leadsToday: number;
}

export default function SearchesPage() {
  const { profiles, setActiveProfileId } = useActiveProfile();
  const [stats, setStats] = React.useState<Record<number, ProfileStats>>({});
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (profiles.length === 0) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all(
      profiles.map(async (p) => {
        const [sources, keywords, overview] = await Promise.all([
          getProfileSources(p.id),
          getProfileKeywords(p.id),
          getAnalyticsOverview(p.id),
        ]);
        return [
          p.id,
          {
            sourceCount: sources.length,
            keywordCount: keywords.length,
            leadsToday: overview.today_leads,
          },
        ] as const;
      })
    )
      .then((entries) => setStats(Object.fromEntries(entries)))
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить поиски');
      })
      .finally(() => setLoading(false));
  }, [profiles]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Мои поиски</h1>
          <p className="text-sm text-muted-foreground">
            Независимые конфигурации поиска клиентов
          </p>
        </div>
        <Link href="/onboarding" className={cn(buttonVariants({ variant: 'default' }))}>
          <Plus className="mr-1.5 h-4 w-4" />
          Создать новый поиск
        </Link>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Загрузка…</p>
      ) : profiles.length === 0 ? (
        <p className="text-sm text-muted-foreground">Поисков пока нет.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {profiles.map((profile) => (
            <SearchProfileCard
              key={profile.id}
              profile={profile}
              stats={stats[profile.id]}
              onSelect={() => setActiveProfileId(profile.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SearchProfileCard({
  profile,
  stats,
  onSelect,
}: {
  profile: SearchProfileRead;
  stats?: ProfileStats;
  onSelect: () => void;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base font-semibold text-foreground">
          🎯 {profile.name}
        </CardTitle>
        <Badge variant={profile.is_active ? 'success' : 'outline'}>
          {profile.is_active ? 'Активен' : 'Приостановлен'}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid grid-cols-3 gap-2 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">Источников</dt>
            <dd className="font-medium">{stats ? stats.sourceCount : '…'}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Ключевых слов</dt>
            <dd className="font-medium">{stats ? stats.keywordCount : '…'}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Лидов сегодня</dt>
            <dd className="font-medium">{stats ? stats.leadsToday : '…'}</dd>
          </div>
        </dl>
        <div className="flex gap-2">
          <Link
            href={`/searches/${profile.id}`}
            onClick={onSelect}
            className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
          >
            Настроить
          </Link>
          <Link
            href={`/searches/${profile.id}/analytics`}
            onClick={onSelect}
            className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
          >
            Аналитика
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
