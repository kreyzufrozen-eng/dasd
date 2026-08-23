'use client';

import * as React from 'react';
import { Plus, Radio, Trash2 } from 'lucide-react';

import {
  addCustomProfileSource,
  ApiError,
  attachProfileSource,
  bulkAttachProfileSources,
  detachProfileSource,
  getProfileSources,
  getSourceCatalog,
  updateProfileSource,
} from '@/lib/api';
import { useActiveProfile } from '@/lib/profile-context';
import type { SearchProfileSourceRead, SourceCatalogEntry } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const SOURCE_CATEGORY_LABELS: Record<string, string> = {
  freelance: '🔥 Фриланс и заказы',
  design: '🎨 Дизайн',
  development: '💻 Разработка',
  marketing: '📈 Маркетинг',
  marketplaces: '🛒 Маркетплейсы',
  business: '💼 Бизнес',
  ai: '🤖 AI и автоматизация',
};

export default function SourcesPage() {
  const { activeProfile, activeProfileId } = useActiveProfile();
  const [links, setLinks] = React.useState<SearchProfileSourceRead[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<number | null>(null);

  const [catalogOpen, setCatalogOpen] = React.useState(false);
  const [catalog, setCatalog] = React.useState<SourceCatalogEntry[]>([]);
  const [catalogLoading, setCatalogLoading] = React.useState(false);
  const [selectAllBusy, setSelectAllBusy] = React.useState(false);

  const [addingCustom, setAddingCustom] = React.useState(false);
  const [customUrl, setCustomUrl] = React.useState('');
  const [customBusy, setCustomBusy] = React.useState(false);

  const fetchLinks = React.useCallback(() => {
    if (!activeProfileId) return;
    setLoading(true);
    setError(null);
    getProfileSources(activeProfileId)
      .then(setLinks)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить источники');
      })
      .finally(() => setLoading(false));
  }, [activeProfileId]);

  React.useEffect(() => {
    fetchLinks();
  }, [fetchLinks]);

  function openCatalog() {
    if (!activeProfileId) return;
    setCatalogOpen(true);
    setCatalogLoading(true);
    getSourceCatalog(activeProfileId)
      .then(setCatalog)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить каталог источников');
      })
      .finally(() => setCatalogLoading(false));
  }

  async function handleToggleCatalogEntry(entry: SourceCatalogEntry) {
    if (!activeProfileId) return;
    setBusyId(entry.id);
    try {
      if (entry.already_added) {
        await detachProfileSource(activeProfileId, entry.id);
      } else {
        await attachProfileSource(activeProfileId, entry.id, true);
      }
      setCatalog((cur) =>
        cur.map((c) =>
          c.id === entry.id
            ? { ...c, already_added: !c.already_added, enabled_for_profile: !c.already_added }
            : c
        )
      );
      fetchLinks();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось изменить источник');
    } finally {
      setBusyId(null);
    }
  }

  async function handleSelectAll() {
    if (!activeProfileId) return;
    const notYetAdded = catalog.filter((c) => !c.already_added).map((c) => c.id);
    if (notYetAdded.length === 0) return;
    setSelectAllBusy(true);
    try {
      await bulkAttachProfileSources(activeProfileId, notYetAdded);
      const added = new Set(notYetAdded);
      setCatalog((cur) =>
        cur.map((c) =>
          added.has(c.id) ? { ...c, already_added: true, enabled_for_profile: true } : c
        )
      );
      fetchLinks();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось добавить источники');
    } finally {
      setSelectAllBusy(false);
    }
  }

  async function handleToggleEnabled(link: SearchProfileSourceRead) {
    if (!activeProfileId) return;
    setBusyId(link.source_id);
    const prev = links;
    setLinks((cur) =>
      cur.map((l) => (l.id === link.id ? { ...l, enabled: !l.enabled } : l))
    );
    try {
      await updateProfileSource(activeProfileId, link.source_id, !link.enabled);
    } catch (err) {
      setLinks(prev);
      setError(err instanceof ApiError ? err.message : 'Не удалось обновить источник');
    } finally {
      setBusyId(null);
    }
  }

  async function handleDetach(link: SearchProfileSourceRead) {
    if (!activeProfileId) return;
    if (!window.confirm(`Убрать источник «${link.source.name}» из этого поиска?`)) return;
    setBusyId(link.source_id);
    try {
      await detachProfileSource(activeProfileId, link.source_id);
      setLinks((cur) => cur.filter((l) => l.id !== link.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось удалить источник');
    } finally {
      setBusyId(null);
    }
  }

  async function handleAddCustom() {
    if (!activeProfileId || !customUrl.trim()) return;
    setCustomBusy(true);
    setError(null);
    const identifier = customUrl.trim().replace(/^https?:\/\/t\.me\//i, '').replace(/^@/, '');
    try {
      await addCustomProfileSource(activeProfileId, {
        name: identifier || customUrl.trim(),
        type: 'telegram',
        url: customUrl.trim(),
        external_identifier: identifier,
      });
      setCustomUrl('');
      setAddingCustom(false);
      fetchLinks();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось добавить источник');
    } finally {
      setCustomBusy(false);
    }
  }

  const byCategory = catalog.reduce<Record<string, SourceCatalogEntry[]>>((acc, s) => {
    const key = s.category || 'other';
    (acc[key] ||= []).push(s);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Источники</h1>
          <p className="text-sm text-muted-foreground">
            {activeProfile ? `Где ищем клиентов для «${activeProfile.name}»` : 'Каналы и чаты, с которых собираются лиды'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setAddingCustom((v) => !v)}>
            <Plus className="mr-1.5 h-4 w-4" />
            Добавить источник
          </Button>
          <Button onClick={openCatalog}>
            <Radio className="mr-1.5 h-4 w-4" />
            Найти источники
          </Button>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {addingCustom && (
        <Card>
          <CardContent className="flex gap-2 pt-4">
            <Input
              value={customUrl}
              onChange={(e) => setCustomUrl(e.target.value)}
              placeholder="https://t.me/example"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleAddCustom();
              }}
            />
            <Button onClick={handleAddCustom} disabled={customBusy || !customUrl.trim()}>
              Добавить
            </Button>
            <Button variant="ghost" onClick={() => setAddingCustom(false)}>
              Отмена
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold text-foreground">
            Подключённые источники
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Загрузка…</p>
          ) : links.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Источники ещё не подключены — нажмите «Найти источники» или добавьте свой чат/канал вручную.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Название</TableHead>
                  <TableHead>Тип</TableHead>
                  <TableHead>Категория</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead className="text-right">Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {links.map((link) => (
                  <TableRow key={link.id}>
                    <TableCell className="font-medium">
                      {link.source.url ? (
                        <a
                          href={link.source.url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="hover:underline"
                        >
                          {link.source.name}
                        </a>
                      ) : (
                        link.source.name
                      )}
                    </TableCell>
                    <TableCell>{link.source.type}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {link.source.category
                        ? SOURCE_CATEGORY_LABELS[link.source.category] ?? link.source.category
                        : '—'}
                    </TableCell>
                    <TableCell>
                      <button
                        onClick={() => handleToggleEnabled(link)}
                        disabled={busyId === link.source_id}
                        className="disabled:opacity-50"
                      >
                        <Badge variant={link.enabled ? 'success' : 'outline'}>
                          {link.enabled ? 'Активен' : 'Отключён'}
                        </Badge>
                      </button>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={busyId === link.source_id}
                        onClick={() => handleDetach(link)}
                        aria-label="Убрать источник"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {catalogOpen && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-semibold text-foreground">
              Каталог источников
            </CardTitle>
            <div className="flex gap-2">
              {catalog.some((c) => !c.already_added) && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={selectAllBusy}
                  onClick={handleSelectAll}
                >
                  {selectAllBusy ? 'Добавляем…' : 'Выбрать все'}
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={() => setCatalogOpen(false)}>
                Закрыть
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {catalogLoading && <p className="text-sm text-muted-foreground">Загрузка…</p>}
            {!catalogLoading && catalog.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Каталог пока пуст — добавьте свои источники вручную кнопкой выше.
              </p>
            )}
            {Object.entries(byCategory).map(([category, items]) => (
              <div key={category} className="space-y-1.5">
                <label className="text-xs text-muted-foreground">
                  {SOURCE_CATEGORY_LABELS[category] ?? category}
                </label>
                <div className="space-y-1">
                  {items.map((entry) => (
                    <label
                      key={entry.id}
                      className="flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
                    >
                      <input
                        type="checkbox"
                        checked={entry.already_added}
                        disabled={busyId === entry.id}
                        onChange={() => handleToggleCatalogEntry(entry)}
                        className="h-4 w-4"
                      />
                      {entry.name}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
