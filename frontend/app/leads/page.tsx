'use client';

import * as React from 'react';

import { ApiError, getLeads, getSourceCatalog, updateLeadStatus } from '@/lib/api';
import { useActiveProfile } from '@/lib/profile-context';
import { LEAD_STATUSES } from '@/lib/types';
import type {
  LeadsQueryParams,
  LeadStatus,
  LeadWithContextRead,
  SourceCatalogEntry,
} from '@/lib/types';
import { STATUS_LABELS } from '@/lib/utils';
import { LeadCard } from '@/components/lead-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface Filters {
  score_min: string;
  score_max: string;
  intent_score_min: string;
  status: string;
  source_id: string;
  service: string;
  date_from: string;
  date_to: string;
  sort: 'newest' | 'score' | 'intent';
}

const DEFAULT_FILTERS: Filters = {
  score_min: '',
  score_max: '',
  intent_score_min: '',
  status: '',
  source_id: '',
  service: '',
  date_from: '',
  date_to: '',
  sort: 'newest',
};

export default function LeadsPage() {
  const { activeProfileId } = useActiveProfile();
  const [filters, setFilters] = React.useState<Filters>(DEFAULT_FILTERS);
  const [leads, setLeads] = React.useState<LeadWithContextRead[]>([]);
  const [sources, setSources] = React.useState<SourceCatalogEntry[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [updatingId, setUpdatingId] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (!activeProfileId) return;
    getSourceCatalog(activeProfileId)
      .then(setSources)
      .catch(() => {
        // Non-fatal — source filter just won't populate.
      });
  }, [activeProfileId]);

  const fetchLeads = React.useCallback(() => {
    if (!activeProfileId) {
      setLeads([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);

    const params: LeadsQueryParams = {
      search_profile_id: activeProfileId,
      sort: filters.sort,
      limit: 50,
    };
    if (filters.score_min) params.score_min = Number(filters.score_min);
    if (filters.score_max) params.score_max = Number(filters.score_max);
    if (filters.intent_score_min) params.intent_score_min = Number(filters.intent_score_min);
    if (filters.status) params.status = filters.status as LeadStatus;
    if (filters.source_id) params.source_id = Number(filters.source_id);
    if (filters.date_from) params.date_from = filters.date_from;
    if (filters.date_to) params.date_to = filters.date_to;

    getLeads(params)
      .then((data) => {
        // service filter is client-side since the API filters by lead_type,
        // not by an individual service string within the services[] array.
        const filtered = filters.service
          ? data.filter((l) =>
              l.services.some((s) =>
                s.toLowerCase().includes(filters.service.toLowerCase())
              )
            )
          : data;
        setLeads(filtered);
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить лиды');
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, activeProfileId]);

  React.useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  function updateFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  async function handleStatusChange(id: number, status: LeadStatus) {
    const prev = leads;
    setUpdatingId(id);
    // Optimistic update
    setLeads((cur) => cur.map((l) => (l.id === id ? { ...l, status } : l)));
    try {
      await updateLeadStatus(id, status);
    } catch (err) {
      // Roll back on failure
      setLeads(prev);
      setError(
        err instanceof ApiError ? err.message : 'Не удалось обновить статус лида'
      );
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Лиды</h1>
          <p className="text-sm text-muted-foreground">
            Найденные и оценённые лиды со всех источников
          </p>
        </div>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant={filters.sort === 'newest' ? 'default' : 'outline'}
            onClick={() => updateFilter('sort', 'newest')}
          >
            Сначала новые
          </Button>
          <Button
            size="sm"
            variant={filters.sort === 'score' ? 'default' : 'outline'}
            onClick={() => updateFilter('sort', 'score')}
          >
            По score
          </Button>
          <Button
            size="sm"
            variant={filters.sort === 'intent' ? 'default' : 'outline'}
            onClick={() => updateFilter('sort', 'intent')}
          >
            🌱 По intent
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold text-foreground">
            Фильтры
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Score от</label>
            <Input
              type="number"
              min={0}
              max={100}
              value={filters.score_min}
              onChange={(e) => updateFilter('score_min', e.target.value)}
              placeholder="0"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Score до</label>
            <Input
              type="number"
              min={0}
              max={100}
              value={filters.score_max}
              onChange={(e) => updateFilter('score_max', e.target.value)}
              placeholder="100"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Intent Score от</label>
            <Input
              type="number"
              min={0}
              max={100}
              value={filters.intent_score_min}
              onChange={(e) => updateFilter('intent_score_min', e.target.value)}
              placeholder="0"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Статус</label>
            <Select
              value={filters.status}
              onChange={(e) => updateFilter('status', e.target.value)}
            >
              <option value="">Все</option>
              {LEAD_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s] ?? s}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Источник</label>
            <Select
              value={filters.source_id}
              onChange={(e) => updateFilter('source_id', e.target.value)}
            >
              <option value="">Все</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Услуга</label>
            <Input
              value={filters.service}
              onChange={(e) => updateFilter('service', e.target.value)}
              placeholder="напр. дизайн"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Дата от</label>
            <Input
              type="date"
              value={filters.date_from}
              onChange={(e) => updateFilter('date_from', e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Дата до</label>
            <Input
              type="date"
              value={filters.date_to}
              onChange={(e) => updateFilter('date_to', e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <Button variant="ghost" size="sm" onClick={() => setFilters(DEFAULT_FILTERS)}>
              Сбросить фильтры
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {loading && <p className="text-sm text-muted-foreground">Загрузка…</p>}

      {!loading && leads.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Лиды не найдены по заданным фильтрам.
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {leads.map((lead) => (
          <LeadCard
            key={lead.id}
            lead={lead}
            onStatusChange={handleStatusChange}
            updating={updatingId === lead.id}
          />
        ))}
      </div>
    </div>
  );
}
