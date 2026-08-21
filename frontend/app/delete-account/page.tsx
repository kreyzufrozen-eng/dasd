'use client';

import Link from 'next/link';

import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function DeleteAccountPage() {
  const { user } = useAuth();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Удаление аккаунта</h1>
        <p className="text-sm text-muted-foreground">
          Как удалить свой аккаунт ReadHunter и что при этом происходит с данными
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">Что произойдёт</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>При удалении аккаунта безвозвратно удаляются:</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>все ваши поиски (Search Profiles) и их настройки;</li>
            <li>ключевые слова и источники, привязанные к вашим поискам;</li>
            <li>найденные лиды и обратная связь по ним;</li>
            <li>привязка Telegram-аккаунта и уведомления;</li>
            <li>данные подписки.</li>
          </ul>
          <p>
            Технические журналы безопасности (audit log) могут сохраняться в обезличенном виде для
            расследования инцидентов — без привязки к удалённому аккаунту.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">Как удалить</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          {user ? (
            <>
              <p>Перейдите в Настройки → Danger Zone → «Удалить аккаунт» и подтвердите действие.</p>
              <Link href="/settings" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                Перейти в настройки
              </Link>
            </>
          ) : (
            <>
              <p>
                Войдите в аккаунт, который хотите удалить, затем перейдите в Настройки → Danger Zone.
              </p>
              <Link href="/login" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                Войти
              </Link>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
