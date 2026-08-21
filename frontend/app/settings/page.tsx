'use client';

import * as React from 'react';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';

import {
  ApiError,
  changePassword,
  deleteAccount,
  downloadDataExport,
  getSubscription,
} from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';
import type { UsageSummary } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { TelegramLoginButton } from '@/components/telegram-login-button';

function UsageBar({ used, max }: { used: number; max: number }) {
  const pct = max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          {used} / {max}
        </span>
        <span className="text-xs text-muted-foreground">{pct}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            'h-full rounded-full transition-all',
            pct >= 100 ? 'bg-destructive' : pct >= 80 ? 'bg-orange-500' : 'bg-primary'
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function AccountCard() {
  const { user, setUser } = useAuth();
  const [currentPassword, setCurrentPassword] = React.useState('');
  const [newPassword, setNewPassword] = React.useState('');
  const [pwSaving, setPwSaving] = React.useState(false);
  const [pwSaved, setPwSaved] = React.useState(false);
  const [pwError, setPwError] = React.useState<string | null>(null);

  if (!user) return null;

  async function handleSetPassword(e: React.FormEvent) {
    e.preventDefault();
    setPwSaving(true);
    setPwError(null);
    setPwSaved(false);
    try {
      await changePassword({
        current_password: user!.has_password ? currentPassword : undefined,
        new_password: newPassword,
      });
      setPwSaved(true);
      setCurrentPassword('');
      setNewPassword('');
    } catch (err) {
      setPwError(err instanceof ApiError ? err.message : 'Не удалось сохранить пароль');
    } finally {
      setPwSaving(false);
    }
  }

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle className="text-base font-semibold text-foreground">Аккаунт</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-1.5">
          <p className="text-xs text-muted-foreground">Email</p>
          <p className="text-sm">{user.email ?? '—'}</p>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">Telegram</p>
            {user.has_telegram && <Badge variant="success">Подключён</Badge>}
          </div>
          {user.has_telegram ? (
            <p className="text-sm">@{user.telegram_username ?? 'аккаунт привязан'}</p>
          ) : (
            <TelegramLoginButton
              mode="link"
              onSuccess={setUser}
              label="Подключить Telegram"
            />
          )}
          {user.has_telegram && (
            <p className="text-xs text-muted-foreground">
              Уведомления о новых лидах будут приходить в этот чат.
            </p>
          )}
        </div>

        <form onSubmit={handleSetPassword} className="space-y-2 border-t border-border pt-4">
          <p className="text-xs text-muted-foreground">
            {user.has_password ? 'Сменить пароль' : 'Задать пароль для входа по email'}
          </p>
          {pwError && (
            <p className="rounded-md border border-destructive/50 bg-destructive/10 p-2 text-xs text-destructive">
              {pwError}
            </p>
          )}
          {user.has_password && (
            <Input
              type="password"
              placeholder="Текущий пароль"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
          )}
          <Input
            type="password"
            placeholder="Новый пароль (минимум 8 символов)"
            autoComplete="new-password"
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
          />
          <Button type="submit" variant="outline" size="sm" disabled={pwSaving}>
            {pwSaving ? 'Сохранение…' : pwSaved ? 'Сохранено' : user.has_password ? 'Сменить пароль' : 'Задать пароль'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function PrivacyCard() {
  const [exporting, setExporting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleExport() {
    setExporting(true);
    setError(null);
    try {
      await downloadDataExport();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось скачать данные');
    } finally {
      setExporting(false);
    }
  }

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle className="text-base font-semibold text-foreground">
          Данные и приватность
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <Link href="/privacy" className="text-primary hover:underline">
            Политика обработки данных
          </Link>
          <Link href="/terms" className="text-primary hover:underline">
            Условия использования
          </Link>
          <Link href="/cookies" className="text-primary hover:underline">
            Cookies
          </Link>
        </div>
        {error && <p className="text-xs text-destructive">{error}</p>}
        <Button type="button" variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
          {exporting ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
          Скачать мои данные
        </Button>
      </CardContent>
    </Card>
  );
}

function DangerZoneCard() {
  const { user, logout } = useAuth();
  const [confirming, setConfirming] = React.useState(false);
  const [password, setPassword] = React.useState('');
  const [deleting, setDeleting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  if (!user) return null;

  async function handleDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount(user!.has_password ? password : undefined);
      await logout();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось удалить аккаунт');
      setDeleting(false);
    }
  }

  return (
    <Card className="max-w-xl border-destructive/40">
      <CardHeader>
        <CardTitle className="text-base font-semibold text-destructive">Danger Zone</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!confirming ? (
          <Button type="button" variant="destructive" size="sm" onClick={() => setConfirming(true)}>
            Удалить аккаунт
          </Button>
        ) : (
          <div className="space-y-3 rounded-md border border-destructive/50 bg-destructive/10 p-3">
            <p className="text-sm text-destructive">
              Это действие необратимо: все ваши поиски, лиды, ключевые слова и настройки будут
              удалены безвозвратно.
            </p>
            {error && <p className="text-xs text-destructive">{error}</p>}
            {user.has_password && (
              <Input
                type="password"
                placeholder="Пароль для подтверждения"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
            <div className="flex gap-2">
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={handleDelete}
                disabled={deleting || (user.has_password && !password)}
              >
                {deleting ? 'Удаление…' : 'Подтвердить удаление'}
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setConfirming(false)}>
                Отмена
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function SettingsPage() {
  const [usage, setUsage] = React.useState<UsageSummary | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setLoading(true);
    getSubscription()
      .then(setUsage)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить данные подписки');
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Настройки</h1>
        <p className="text-sm text-muted-foreground">Аккаунт, тариф и приватность</p>
      </div>

      <AccountCard />

      {error && (
        <p className="max-w-xl rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Загрузка…</p>
      ) : usage ? (
        <Card className="max-w-xl">
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base font-semibold text-foreground">
              Тариф «{usage.plan_name}»
            </CardTitle>
            <span className="text-sm text-muted-foreground">
              {usage.price != null ? `${usage.price.toLocaleString('ru-RU')} ${usage.currency}/мес` : 'Бесплатно'}
            </span>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground">Поисков создано</p>
              <UsageBar used={usage.search_profiles_used} max={usage.max_search_profiles} />
            </div>
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground">
                AI-анализов в этом месяце (с{' '}
                {new Date(usage.period_start).toLocaleDateString('ru-RU', {
                  day: '2-digit',
                  month: '2-digit',
                })}
                )
              </p>
              <UsageBar
                used={usage.ai_analyses_used_this_period}
                max={usage.max_ai_analyses_per_month}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Источников на один поиск: до {usage.max_sources_per_profile}
            </p>
            <p className="pt-2 text-xs text-muted-foreground">
              Платные тарифы и повышение лимитов появятся в одном из следующих обновлений.
            </p>
          </CardContent>
        </Card>
      ) : null}

      <PrivacyCard />
      <DangerZoneCard />
    </div>
  );
}
