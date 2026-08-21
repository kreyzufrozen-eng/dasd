'use client';

import * as React from 'react';
import { Loader2, Send } from 'lucide-react';

import {
  ApiError,
  completeTelegramLogin,
  getTelegramLoginStatus,
  startTelegramLink,
  startTelegramLogin,
} from '@/lib/api';
import type { UserRead } from '@/lib/types';
import { Button } from '@/components/ui/button';

const POLL_INTERVAL_MS = 2000;

interface Props {
  onSuccess: (user: UserRead) => void;
  /** Required before a brand-new account can be created — ignored by the
   * backend when the token turns out to belong to an existing user, and
   * always irrelevant in "link" mode (the caller already has an account). */
  acceptedLegal?: boolean;
  label?: string;
  /** 'login': no session yet, may create a new account. 'link': caller is
   * already authenticated and is attaching Telegram to their own account
   * (see Settings). */
  mode?: 'login' | 'link';
}

type Phase = 'idle' | 'waiting' | 'error';

export function TelegramLoginButton({
  onSuccess,
  acceptedLegal = false,
  label,
  mode = 'login',
}: Props) {
  const [phase, setPhase] = React.useState<Phase>('idle');
  const [error, setError] = React.useState<string | null>(null);
  const pollTimer = React.useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = React.useCallback(() => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  React.useEffect(() => stopPolling, [stopPolling]);

  async function handleStart() {
    setError(null);
    setPhase('waiting');
    try {
      const started = await (mode === 'link' ? startTelegramLink() : startTelegramLogin());
      window.open(started.deep_link, '_blank', 'noopener,noreferrer');

      pollTimer.current = setInterval(async () => {
        try {
          const status = await getTelegramLoginStatus(started.token);
          if (status.status === 'confirmed') {
            stopPolling();
            const user = await completeTelegramLogin(started.token, acceptedLegal);
            onSuccess(user);
          } else if (status.status === 'expired') {
            stopPolling();
            setError('Время ожидания истекло — попробуйте ещё раз');
            setPhase('error');
          }
        } catch (err) {
          stopPolling();
          setError(err instanceof ApiError ? err.message : 'Не удалось завершить вход');
          setPhase('error');
        }
      }, POLL_INTERVAL_MS);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось начать вход через Telegram');
      setPhase('error');
    }
  }

  return (
    <div className="space-y-2">
      <Button
        type="button"
        className="w-full gap-2 bg-[#26A5E4] text-white hover:bg-[#1e8bc3]"
        onClick={handleStart}
        disabled={phase === 'waiting'}
      >
        {phase === 'waiting' ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
        {phase === 'waiting'
          ? 'Ждём подтверждения в Telegram…'
          : label ?? (mode === 'link' ? 'Подключить Telegram' : 'Войти через Telegram')}
      </Button>
      {phase === 'waiting' && (
        <p className="text-center text-xs text-muted-foreground">
          Откройте Telegram и нажмите «Start» в открывшемся чате с ботом
        </p>
      )}
      {error && <p className="text-center text-xs text-destructive">{error}</p>}
    </div>
  );
}
