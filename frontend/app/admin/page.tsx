'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import {
  Database,
  Inbox,
  KeyRound,
  Radio,
  ShieldCheck,
  TrendingUp,
  Users,
} from 'lucide-react';

import {
  ApiError,
  getAdminOverview,
  getAdminUserProfiles,
  getAdminUsers,
  updateAdminUser,
} from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import type { AdminOverview, AdminSearchProfileDetail, AdminUserRead } from '@/lib/types';
import { formatDate } from '@/lib/utils';
import { StatCard } from '@/components/stat-card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

function formatLastLogin(value: string | null): string {
  if (!value) return 'Ни разу';
  return formatDate(value);
}

export default function AdminPage() {
  const { user: currentUser, loading: authLoading } = useAuth();
  const router = useRouter();
  const [overview, setOverview] = React.useState<AdminOverview | null>(null);
  const [users, setUsers] = React.useState<AdminUserRead[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<number | null>(null);
  const [profileDialogUser, setProfileDialogUser] = React.useState<AdminUserRead | null>(null);
  const [profiles, setProfiles] = React.useState<AdminSearchProfileDetail[]>([]);
  const [profilesLoading, setProfilesLoading] = React.useState(false);
  const [profilesError, setProfilesError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!authLoading && currentUser && !currentUser.is_admin) {
      router.replace('/');
    }
  }, [authLoading, currentUser, router]);

  const fetchAll = React.useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([getAdminOverview(), getAdminUsers()])
      .then(([overviewData, usersData]) => {
        setOverview(overviewData);
        setUsers(usersData);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError ? err.message : 'Не удалось загрузить данные админки'
        );
      })
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    if (currentUser?.is_admin) {
      fetchAll();
    }
  }, [currentUser, fetchAll]);

  async function handleToggleAdmin(target: AdminUserRead) {
    setBusyId(target.id);
    const prev = users;
    setUsers((cur) =>
      cur.map((u) => (u.id === target.id ? { ...u, is_admin: !u.is_admin } : u))
    );
    try {
      await updateAdminUser(target.id, { is_admin: !target.is_admin });
    } catch (err) {
      setUsers(prev);
      setError(err instanceof ApiError ? err.message : 'Не удалось обновить пользователя');
    } finally {
      setBusyId(null);
    }
  }

  function openProfileDialog(target: AdminUserRead) {
    setProfileDialogUser(target);
    setProfiles([]);
    setProfilesError(null);
    setProfilesLoading(true);
    getAdminUserProfiles(target.id)
      .then(setProfiles)
      .catch((err: unknown) => {
        setProfilesError(err instanceof ApiError ? err.message : 'Не удалось загрузить профиль');
      })
      .finally(() => setProfilesLoading(false));
  }

  async function handleToggleActive(target: AdminUserRead) {
    setBusyId(target.id);
    const prev = users;
    setUsers((cur) =>
      cur.map((u) => (u.id === target.id ? { ...u, is_active: !u.is_active } : u))
    );
    try {
      await updateAdminUser(target.id, { is_active: !target.is_active });
    } catch (err) {
      setUsers(prev);
      setError(err instanceof ApiError ? err.message : 'Не удалось обновить пользователя');
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Админка</h1>
        <p className="text-sm text-muted-foreground">
          Пользователи и общая статистика системы
        </p>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          title="Пользователей"
          value={overview ? overview.total_users : loading ? '…' : 0}
          icon={Users}
        />
        <StatCard
          title="Лидов всего"
          value={overview ? overview.total_leads : loading ? '…' : 0}
          icon={TrendingUp}
        />
        <StatCard
          title="Лидов сегодня"
          value={overview ? overview.leads_today : loading ? '…' : 0}
          icon={Inbox}
        />
        <StatCard
          title="Сообщений собрано"
          value={overview ? overview.total_raw_items : loading ? '…' : 0}
          icon={Database}
        />
        <StatCard
          title="Источников"
          value={
            overview ? `${overview.active_sources}/${overview.total_sources}` : loading ? '…' : 0
          }
          icon={Radio}
        />
        <StatCard
          title="Ключевых слов"
          value={overview ? overview.total_keywords : loading ? '…' : 0}
          icon={KeyRound}
        />
        <StatCard
          title="Профилей поиска"
          value={overview ? overview.total_search_profiles : loading ? '…' : 0}
          icon={ShieldCheck}
        />
        <StatCard
          title="База данных"
          value={overview ? overview.database_status : loading ? '…' : '—'}
          icon={Database}
          accentClassName={overview?.database_status === 'ok' ? 'text-emerald-500' : 'text-destructive'}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold text-foreground">
            Пользователи
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Загрузка…</p>
          ) : users.length === 0 ? (
            <p className="text-sm text-muted-foreground">Пользователей ещё нет.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Имя</TableHead>
                  <TableHead>Профилей</TableHead>
                  <TableHead>Лидов</TableHead>
                  <TableHead>Регистрация</TableHead>
                  <TableHead>Последний вход</TableHead>
                  <TableHead>Роль</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead className="text-right">Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => {
                  const isSelf = currentUser?.id === u.id;
                  return (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">
                        {u.email || (u.telegram_username && `@${u.telegram_username}`) || '—'}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {u.name || '—'}
                      </TableCell>
                      <TableCell>{u.search_profile_count}</TableCell>
                      <TableCell>{u.lead_count}</TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">
                        {formatDate(u.created_at)}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">
                        {formatLastLogin(u.last_login_at)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={u.is_admin ? 'success' : 'outline'}>
                          {u.is_admin ? 'Админ' : 'Пользователь'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={u.is_active ? 'success' : 'destructive'}>
                          {u.is_active ? 'Активен' : 'Заблокирован'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right space-x-2">
                        <Button variant="outline" size="sm" onClick={() => openProfileDialog(u)}>
                          Профиль
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={busyId === u.id || isSelf}
                          title={isSelf ? 'Нельзя изменить свою же роль' : undefined}
                          onClick={() => handleToggleAdmin(u)}
                        >
                          {u.is_admin ? 'Забрать админку' : 'Сделать админом'}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={busyId === u.id || isSelf}
                          title={isSelf ? 'Нельзя заблокировать себя' : undefined}
                          onClick={() => handleToggleActive(u)}
                        >
                          {u.is_active ? 'Заблокировать' : 'Разблокировать'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={profileDialogUser !== null} onOpenChange={(open) => !open && setProfileDialogUser(null)}>
        <DialogContent
          className="max-h-[85vh] max-w-2xl overflow-y-auto"
          onClose={() => setProfileDialogUser(null)}
        >
          <DialogHeader>
            <DialogTitle>
              Профиль —{' '}
              {profileDialogUser?.email ||
                (profileDialogUser?.telegram_username && `@${profileDialogUser.telegram_username}`) ||
                profileDialogUser?.id}
            </DialogTitle>
          </DialogHeader>

          {profilesLoading ? (
            <p className="text-sm text-muted-foreground">Загрузка…</p>
          ) : profilesError ? (
            <p className="text-sm text-destructive">{profilesError}</p>
          ) : profiles.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              У пользователя нет поисковых профилей — онбординг не пройден.
            </p>
          ) : (
            <div className="space-y-6">
              {profiles.map((p) => {
                const customSources = p.sources.filter((s) => s.is_custom);
                const catalogCount = p.sources.length - customSources.length;
                return (
                  <div key={p.id} className="space-y-3 rounded-md border border-border p-4">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="font-semibold text-foreground">{p.name}</h3>
                      <Badge variant={p.is_active ? 'success' : 'outline'}>
                        {p.is_active ? 'Активен' : 'Отключён'}
                      </Badge>
                    </div>

                    <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
                      <div>
                        <dt className="text-muted-foreground">Профессия</dt>
                        <dd className="text-foreground">{p.profession || '—'}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Целевые клиенты</dt>
                        <dd className="text-foreground">{p.target_clients || '—'}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">География</dt>
                        <dd className="text-foreground">{p.geography || '—'}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Создан</dt>
                        <dd className="text-foreground">{formatDate(p.created_at)}</dd>
                      </div>
                    </dl>

                    {p.profession_description && (
                      <div className="text-sm">
                        <p className="text-muted-foreground">Описание от пользователя</p>
                        <p className="whitespace-pre-wrap text-foreground">
                          {p.profession_description}
                        </p>
                      </div>
                    )}

                    <div className="text-sm">
                      <p className="mb-1 text-muted-foreground">Услуги</p>
                      <div className="flex flex-wrap gap-1">
                        {p.services.length > 0 ? (
                          p.services.map((s) => (
                            <Badge key={s} variant="outline">
                              {s}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-foreground">—</span>
                        )}
                      </div>
                    </div>

                    {p.preferred_niches.length > 0 && (
                      <div className="text-sm">
                        <p className="mb-1 text-muted-foreground">Приоритетные ниши</p>
                        <div className="flex flex-wrap gap-1">
                          {p.preferred_niches.map((n) => (
                            <Badge key={n} variant="outline">
                              {n}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {p.excluded_niches.length > 0 && (
                      <div className="text-sm">
                        <p className="mb-1 text-muted-foreground">Исключения</p>
                        <div className="flex flex-wrap gap-1">
                          {p.excluded_niches.map((n) => (
                            <Badge key={n} variant="outline">
                              {n}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="text-sm">
                      <p className="mb-1 text-muted-foreground">
                        Источники — {p.sources.length} всего ({catalogCount} из каталога,{' '}
                        {customSources.length} добавил сам)
                      </p>
                      {customSources.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {customSources.map((s) => (
                            <Badge key={s.id} variant="secondary">
                              {s.name}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="text-sm">
                      <p className="mb-1 text-muted-foreground">
                        Ключевые слова — {p.keywords.length}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {p.keywords.map((k) => (
                          <Badge
                            key={`${k.text}-${k.category}`}
                            variant={k.enabled ? 'outline' : 'secondary'}
                          >
                            {k.text}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
