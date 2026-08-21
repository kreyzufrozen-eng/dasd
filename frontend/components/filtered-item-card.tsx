'use client';

import * as React from 'react';
import { ThumbsDown, ThumbsUp } from 'lucide-react';

import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ApiError, submitLeadFeedback } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import type { LeadWithContextRead } from '@/lib/types';

export interface FilteredItemCardProps {
  lead: LeadWithContextRead;
  // Called after a successful 👍 "это всё-таки лид" — the item should
  // disappear from this list (it now has is_lead=true, so it belongs on
  // /leads instead), same as the ТЗ's "должно переместиться в лиды".
  onMarkedRelevant?: (leadId: number) => void;
}

// Shows a Lead the AI evaluated and rejected (is_lead=false) — same shape
// as a qualifying lead, just with the AI's reasoning surfaced instead of
// the CRM status workflow (there's nothing to manage on a rejected item).
export function FilteredItemCard({ lead, onMarkedRelevant }: FilteredItemCardProps) {
  const [busy, setBusy] = React.useState(false);
  const [markedIrrelevant, setMarkedIrrelevant] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleFeedback(action: 'relevant' | 'irrelevant') {
    setBusy(true);
    setError(null);
    try {
      await submitLeadFeedback(lead.id, { action });
      if (action === 'relevant') {
        onMarkedRelevant?.(lead.id);
      } else {
        setMarkedIrrelevant(true);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить отметку');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="opacity-90">
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2 space-y-0">
        <div className="flex items-center gap-2">
          <Badge variant="cold" className="text-sm">
            {lead.lead_score}
          </Badge>
          {lead.intent_score > 0 ? (
            <Badge variant="warm" className="text-sm" title="Intent Score — вероятность скорой потребности в сайте">
              🌱 Скрытый спрос: {lead.intent_score}
            </Badge>
          ) : (
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Не лид
            </span>
          )}
        </div>
        <span className="text-xs text-muted-foreground">{formatDate(lead.created_at)}</span>
      </CardHeader>
      <CardContent className="space-y-3">
        {lead.summary && <p className="text-sm font-medium">{lead.summary}</p>}

        {lead.reasoning && (
          <div className="rounded-md border border-border bg-muted/30 p-2.5">
            <p className="text-xs font-medium text-muted-foreground">Почему AI отклонил:</p>
            <p className="text-xs">{lead.reasoning}</p>
          </div>
        )}

        {lead.raw_text && (
          <p className="whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
            {lead.raw_text}
          </p>
        )}

        {lead.intent_signals.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">
              Признаки скорой потребности в сайте:
            </p>
            <div className="flex flex-wrap gap-1">
              {lead.intent_signals.map((signal) => (
                <Badge key={signal} variant="warm">
                  🌱 {signal}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {lead.negative_signals.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Сигналы отклонения:</p>
            <div className="flex flex-wrap gap-1">
              {lead.negative_signals.map((signal) => (
                <Badge key={signal} variant="outline" className="border-destructive/40 text-destructive">
                  {signal}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
          <div>
            <dt className="text-muted-foreground">Источник</dt>
            <dd>{lead.source_name ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Автор</dt>
            <dd>
              {lead.author_name || lead.author_username
                ? `${lead.author_name ?? ''}${
                    lead.author_username ? ` (@${lead.author_username})` : ''
                  }`
                : '—'}
            </dd>
          </div>
        </dl>

        {lead.raw_url && (
          <a
            href={lead.raw_url}
            target="_blank"
            rel="noreferrer noopener"
            className="text-xs text-primary underline-offset-4 hover:underline"
          >
            Открыть источник →
          </a>
        )}

        {error && <p className="text-xs text-destructive">{error}</p>}

        <div className="flex items-center gap-1.5 border-t border-border pt-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleFeedback('relevant')}
            disabled={busy}
          >
            <ThumbsUp className="mr-1.5 h-3.5 w-3.5" />
            Это всё-таки лид
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleFeedback('irrelevant')}
            disabled={busy || markedIrrelevant}
          >
            <ThumbsDown className="mr-1.5 h-3.5 w-3.5" />
            {markedIrrelevant ? 'Отмечено' : 'Точно не лид'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
