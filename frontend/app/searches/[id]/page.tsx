'use client';

import * as React from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Plus, Trash2, X } from 'lucide-react';

import {
  ApiError,
  deleteSearchProfile,
  getSearchProfile,
  updateSearchProfile,
} from '@/lib/api';
import { useActiveProfile } from '@/lib/profile-context';
import type { SearchProfileRead } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const TABS = [
  'Общее',
  'Что искать',
  'Исключения',
  'AI-настройка',
  'Уведомления',
] as const;
type Tab = (typeof TABS)[number];

function ChipEditor({
  items,
  onChange,
  placeholder,
}: {
  items: string[];
  onChange: (items: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = React.useState('');
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <Badge key={item} variant="outline" className="gap-1 pr-1">
            {item}
            <button
              onClick={() => onChange(items.filter((i) => i !== item))}
              className="rounded-full p-0.5 hover:bg-accent"
              aria-label={`Удалить ${item}`}
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={placeholder}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && draft.trim()) {
              e.preventDefault();
              onChange([...items, draft.trim()]);
              setDraft('');
            }
          }}
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            if (draft.trim()) {
              onChange([...items, draft.trim()]);
              setDraft('');
            }
          }}
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

export default function SearchProfileSettingsPage() {
  const params = useParams<{ id: string }>();
  const profileId = Number(params.id);
  const router = useRouter();
  const { refresh: refreshProfiles } = useActiveProfile();

  const [profile, setProfile] = React.useState<SearchProfileRead | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [tab, setTab] = React.useState<Tab>('Общее');

  React.useEffect(() => {
    if (!profileId) return;
    setLoading(true);
    getSearchProfile(profileId)
      .then(setProfile)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить поиск');
      })
      .finally(() => setLoading(false));
  }, [profileId]);

  function patch<K extends keyof SearchProfileRead>(key: K, value: SearchProfileRead[K]) {
    setProfile((p) => (p ? { ...p, [key]: value } : p));
    setSaved(false);
  }

  async function handleSave() {
    if (!profile) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateSearchProfile(profile.id, {
        name: profile.name,
        profession: profile.profession ?? undefined,
        profession_description: profile.profession_description ?? undefined,
        services: profile.services,
        excluded_niches: profile.excluded_niches,
        preferred_niches: profile.preferred_niches,
        min_budget: profile.min_budget,
        max_budget: profile.max_budget,
        geography: profile.geography ?? undefined,
        languages: profile.languages,
        ai_profile_context: profile.ai_profile_context ?? undefined,
        notification_threshold: profile.notification_threshold,
        is_active: profile.is_active,
      });
      setProfile(updated);
      setSaved(true);
      await refreshProfiles();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить изменения');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!profile) return;
    if (
      !window.confirm(
        `Удалить поиск «${profile.name}»? Все связанные лиды, ключевые слова и источники будут удалены безвозвратно.`
      )
    )
      return;
    setSaving(true);
    setError(null);
    try {
      await deleteSearchProfile(profile.id);
      await refreshProfiles();
      router.push('/searches');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось удалить поиск');
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Загрузка…</p>;
  }

  if (error && !profile) {
    return (
      <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
        {error}
      </p>
    );
  }

  if (!profile) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">🎯 {profile.name}</h1>
          <p className="text-sm text-muted-foreground">Настройка поиска</p>
        </div>
        <div className="flex gap-2">
          <Button variant="destructive" onClick={handleDelete} disabled={saving}>
            <Trash2 className="mr-1.5 h-4 w-4" />
            Удалить поиск
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? 'Сохранение…' : saved ? 'Сохранено' : 'Сохранить'}
          </Button>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-1">
        {TABS.map((t) => (
          <Button
            key={t}
            size="sm"
            variant={tab === t ? 'default' : 'outline'}
            onClick={() => setTab(t)}
          >
            {t}
          </Button>
        ))}
        <Link href="/keywords" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
          Ключевые слова →
        </Link>
        <Link href="/sources" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
          Источники →
        </Link>
        <Link
          href={`/searches/${profileId}/analytics`}
          className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
        >
          Аналитика →
        </Link>
      </div>

      {tab === 'Общее' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-foreground">Общее</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Название поиска</label>
              <Input value={profile.name} onChange={(e) => patch('name', e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Специализация</label>
              <Input
                value={profile.profession ?? ''}
                onChange={(e) => patch('profession', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Услуги</label>
              <ChipEditor
                items={profile.services}
                onChange={(v) => patch('services', v)}
                placeholder="Добавить услугу"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">География</label>
                <Input
                  value={profile.geography ?? ''}
                  onChange={(e) => patch('geography', e.target.value)}
                  placeholder="напр. Россия, удалённо"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Языки</label>
                <ChipEditor
                  items={profile.languages}
                  onChange={(v) => patch('languages', v)}
                  placeholder="напр. русский"
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={profile.is_active}
                onChange={(e) => patch('is_active', e.target.checked)}
              />
              Поиск активен
            </label>
          </CardContent>
        </Card>
      )}

      {tab === 'Что искать' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-foreground">
              Какие заявки вы хотите получать?
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <textarea
              value={profile.profession_description ?? ''}
              onChange={(e) => patch('profession_description', e.target.value)}
              rows={6}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              placeholder="Опишите своими словами, какие заказы вам нужны"
            />
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Приоритетные ниши</label>
              <ChipEditor
                items={profile.preferred_niches}
                onChange={(v) => patch('preferred_niches', v)}
                placeholder="Добавить нишу"
              />
            </div>
          </CardContent>
        </Card>
      )}

      {tab === 'Исключения' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-foreground">
              Что не показывать
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ChipEditor
              items={profile.excluded_niches}
              onChange={(v) => patch('excluded_niches', v)}
              placeholder="Добавить исключение"
            />
          </CardContent>
        </Card>
      )}

      {tab === 'AI-настройка' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-foreground">
              Контекст для AI
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <textarea
              value={profile.ai_profile_context ?? ''}
              onChange={(e) => patch('ai_profile_context', e.target.value)}
              rows={5}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Мин. бюджет</label>
                <Input
                  type="number"
                  min={0}
                  value={profile.min_budget ?? ''}
                  onChange={(e) =>
                    patch('min_budget', e.target.value ? Number(e.target.value) : null)
                  }
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Макс. бюджет</label>
                <Input
                  type="number"
                  min={0}
                  value={profile.max_budget ?? ''}
                  onChange={(e) =>
                    patch('max_budget', e.target.value ? Number(e.target.value) : null)
                  }
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === 'Уведомления' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-foreground">Уведомления</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">
                Минимальный Match Score для уведомления: {profile.notification_threshold}
              </label>
              <input
                type="range"
                min={0}
                max={100}
                value={profile.notification_threshold}
                onChange={(e) => patch('notification_threshold', Number(e.target.value))}
                className="w-full"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Уведомления сейчас приходят через Telegram-бота на аккаунт, привязанный к системе.
              Отдельная привязка Telegram-чата для каждого пользователя появится в одном из
              следующих обновлений.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
