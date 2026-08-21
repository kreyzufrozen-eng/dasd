'use client';

import * as React from 'react';

import { ApiError, getLeads, getSourceCatalog } from '@/lib/api';
import { useActiveProfile } from '@/lib/profile-context';
import type { LeadsQueryParams, LeadWithContextRead, SourceCatalogEntry } from '@/lib/types';
import { FilteredItemCard } from '@/components/filtered-item-card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface Filters {
  source_id: string;
  date_from: string;
  date_to: string;
}

const DEFAULT_FILTERS: Filters = {
  source_id: '',
  date_from: '',
  date_to: '',
};

// Messages the AI pipeline actually analyzed and decided were NOT leads
// (Lead.is_lead = false). Items rejected earlier by the keyword pre-filter
// never reach the AI and never become a Lead row, so they can't be shown
// here — this view is specifically "what the AI looked at and turned down".
export default function FilteredPage() {
  const { activeProfileId } = useActiveProfile();
  const [filters, setFilters] = React.useState<Filters>(DEFAULT_FILTERS);
  const [items, setItems] = React.useState<LeadWithContextRead[]>([]);
  const [sources, setSources] = React.useState<SourceCatalogEntry[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!activeProfileId) return;
    getSourceCatalog(activeProfileId)
      .then(setSources)
      .catch(() => {
        // Non-fatal — source filter just won't populate.
      });
  }, [activeProfileId]);

  const fetchItems = React.useCallback(() => {
    if (!activeProfileId) {
      setItems([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);

    const params: LeadsQueryParams = {
      search_profile_id: activeProfileId,
      is_lead: false,
      sort: 'newest',
      limit: 50,
    };
    if (filters.source_id) params.source_id = Number(filters.source_id);
    if (filters.date_from) params.date_from = filters.date_from;
    if (filters.date_to) params.date_to = filters.date_to;

    getLeads(params)
      .then(setItems)
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError ? err.message : 'Не удалось загрузить отфильтрованные сообщения'
        );
      })
      .finally(() => setLoading(false));
  }, [filters, activeProfileId]);

  React.useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  function updateFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Отфильтровано ИИ</h1>
        <p className="text-sm text-muted-foreground">
          Сообщения, которые прошли AI-анализ, но были признаны не лидами — вместе с причиной
          отклонения
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold text-foreground">Фильтры</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-4">
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

      {!loading && items.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Отфильтрованных сообщений не найдено по заданным фильтрам.
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => (
          <FilteredItemCard
            key={item.id}
            lead={item}
            onMarkedRelevant={(leadId) =>
              setItems((cur) => cur.filter((i) => i.id !== leadId))
            }
          />
        ))}
      </div>
    </div>
  );
}
