'use client';

import * as React from 'react';
import Link from 'next/link';

import { ApiError, loginUser } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TelegramLoginButton } from '@/components/telegram-login-button';

export default function LoginPage() {
  const { setUser } = useAuth();
  const [acceptedLegal, setAcceptedLegal] = React.useState(false);
  const [showEmailForm, setShowEmailForm] = React.useState(false);
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const user = await loginUser({ email, password });
      setUser(user);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось войти');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-semibold text-foreground">
            Вход в ReadHunter
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </p>
          )}

          <label className="flex items-start gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={acceptedLegal}
              onChange={(e) => setAcceptedLegal(e.target.checked)}
              className="mt-0.5 h-3.5 w-3.5 shrink-0"
            />
            <span>
              Согласен(на) с{' '}
              <Link href="/privacy" target="_blank" className="text-primary hover:underline">
                политикой обработки данных
              </Link>{' '}
              и{' '}
              <Link href="/terms" target="_blank" className="text-primary hover:underline">
                условиями использования
              </Link>
            </span>
          </label>

          <TelegramLoginButton onSuccess={setUser} acceptedLegal={acceptedLegal} />

          <div className="relative py-1 text-center text-xs text-muted-foreground">
            <span className="relative bg-card px-2">или</span>
            <div className="absolute inset-x-0 top-1/2 -z-10 h-px bg-border" />
          </div>

          {!showEmailForm ? (
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={() => setShowEmailForm(true)}
            >
              Войти по email и паролю
            </Button>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Email</label>
                <Input
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Пароль</label>
                <Input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <Button type="submit" variant="outline" className="w-full" disabled={submitting}>
                {submitting ? 'Вход…' : 'Войти'}
              </Button>
            </form>
          )}

          <p className="text-center text-sm text-muted-foreground">
            Нет аккаунта?{' '}
            <Link href="/register" className="text-primary hover:underline">
              Зарегистрироваться
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
