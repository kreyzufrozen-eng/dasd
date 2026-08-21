import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || 'support@readhunter.example';

export default function SupportPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Поддержка</h1>
        <p className="text-sm text-muted-foreground">
          Вопросы по работе сервиса, обработке персональных данных и удалению данных
        </p>
      </div>

      <Card>
        <CardContent className="space-y-3 pt-6 text-sm">
          <p>
            По любым вопросам — включая запросы на экспорт, исправление или удаление персональных
            данных — напишите нам:
          </p>
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-lg font-medium text-primary hover:underline">
            {SUPPORT_EMAIL}
          </a>
          <p className="text-xs text-muted-foreground">
            Экспорт и удаление данных также доступны самостоятельно в Настройках аккаунта.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
