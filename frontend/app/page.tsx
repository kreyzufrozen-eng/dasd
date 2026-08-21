'use client';

import * as React from 'react';
import { CheckCircle2, Flame, Sparkles, TrendingUp } from 'lucide-react';

import { ApiError, getAnalyticsOverview, getLeads } from '@/lib/api';
import { useActiveProfile } from '@/lib/profile-context';
import type { AnalyticsOverview, LeadWithContextRead } from '@/lib/types';
import { formatDate, scoreTier, STATUS_LABELS } from '@/lib/utils';
import { StatCard } from '@/components/stat-card';
import { SimpleBarChart } from '@/components/simple-bar-chart';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export default function DashboardPage() {
  const { activeProfile, activeProfileId } = useActiveProfile();
  const [overview, setOverview] = React.useState<AnalyticsOverview | null>(null);
  const [leads, setLeads] = React.useState<LeadWithContextRead[]>([]);
  const [range, setRange] = React.useState<'7' | '30'>('7');
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!activeProfileId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      getAnalyticsOverview(activeProfileId),
      getLeads({ search_profile_id: activeProfileId, sort: 'newest', limit: 10 }),
    ])
      .then(([overviewData, leadsData]) => {
        if (cancelled) return;
        setOverview(overviewData);
        setLeads(leadsData);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить данные');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeProfileId]);

  const chartData =
    range === '7' ? overview?.leads_last_7_days : overview?.leads_last_30_days;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            {activeProfile ? `🎯 ${activeProfile.name}` : 'Дашборд'}
          </h1>
          <p className="mt-0.5 flex items-center gap-2 text-sm text-muted-foreground">
            {activeProfile ? (
              <Badge variant={activeProfile.is_active ? 'success' : 'outline'}>
                {activeProfile.is_active ? '🟢 Поиск активен' : '⏸ Приостановлен'}
              </Badge>
            ) : (
              'Обзор найденных лидов и активности источников'
            )}
          </p>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          title="Сегодня найдено"
          value={overview ? overview.today_leads : loading ? '…' : 0}
          icon={Sparkles}
        />
        <StatCard
          title="Горячих лидов"
          value={overview ? overview.hot_leads : loading ? '…' : 0}
          icon={Flame}
          accentClassName="text-red-500"
        />
        <StatCard
          title="Всего лидов"
          value={overview ? overview.total_leads : loading ? '…' : 0}
          icon={TrendingUp}
        />
        <StatCard
          title="Конвертировано"
          value={overview ? overview.converted_leads : loading ? '…' : 0}
          icon={CheckCircle2}
          accentClassName="text-emerald-500"
        />
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base font-semibold text-foreground">
            Лиды по дням
          </CardTitle>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant={range === '7' ? 'default' : 'outline'}
              onClick={() => setRange('7')}
            >
              7 дней
            </Button>
            <Button
              size="sm"
              variant={range === '30' ? 'default' : 'outline'}
              onClick={() => setRange('30')}
            >
              30 дней
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <SimpleBarChart data={chartData ?? []} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">
            Последние лиды
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Score</TableHead>
                <TableHead>Описание</TableHead>
                <TableHead>Услуга</TableHead>
                <TableHead>Источник</TableHead>
                <TableHead>Дата</TableHead>
                <TableHead>Статус</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leads.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    Лидов пока нет
                  </TableCell>
                </TableRow>
              )}
              {leads.map((lead) => {
                const tier = scoreTier(lead.lead_score);
                const badgeVariant =
                  tier === 'hot' ? 'hot' : tier === 'warm' ? 'warm' : 'cold';
                return (
                  <TableRow key={lead.id}>
                    <TableCell>
                      <Badge variant={badgeVariant}>{lead.lead_score}</Badge>
                    </TableCell>
                    <TableCell className="max-w-xs truncate" title={lead.summary ?? ''}>
                      {lead.summary || '—'}
                    </TableCell>
                    <TableCell className="max-w-[10rem] truncate">
                      {lead.services.join(', ') || '—'}
                    </TableCell>
                    <TableCell>{lead.source_name ?? '—'}</TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(lead.created_at)}
                    </TableCell>
                    <TableCell>{STATUS_LABELS[lead.status] ?? lead.status}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
