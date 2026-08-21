'use client';

import * as React from 'react';
import { Bookmark, Copy, ExternalLink, MessageSquareText, ThumbsDown } from 'lucide-react';

import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { ApiError, submitLeadFeedback } from '@/lib/api';
import { classifyLead, cn, formatBudget, formatDate, STATUS_LABELS } from '@/lib/utils';
import { LEAD_STATUSES, type LeadStatus, type LeadWithContextRead } from '@/lib/types';

export interface LeadCardProps {
  lead: LeadWithContextRead;
  onStatusChange: (id: number, status: LeadStatus) => void;
  updating?: boolean;
}

export function LeadCard({ lead, onStatusChange, updating }: LeadCardProps) {
  const classification = classifyLead(lead.lead_score, lead.intent_score);
  const [feedbackBusy, setFeedbackBusy] = React.useState(false);
  const [feedbackDone, setFeedbackDone] = React.useState<'saved' | 'irrelevant' | null>(null);
  const [copied, setCopied] = React.useState(false);
  const [feedbackError, setFeedbackError] = React.useState<string | null>(null);

  async function handleFeedback(action: 'saved' | 'irrelevant') {
    setFeedbackBusy(true);
    setFeedbackError(null);
    try {
      await submitLeadFeedback(lead.id, { action });
      setFeedbackDone(action);
    } catch (err) {
      setFeedbackError(err instanceof ApiError ? err.message : 'Не удалось сохранить отметку');
    } finally {
      setFeedbackBusy(false);
    }
  }

  async function handleCopy() {
    if (!lead.raw_text) return;
    await navigator.clipboard.writeText(lead.raw_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2 space-y-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={classification.badgeVariant} className="text-sm">
            {classification.emoji} {lead.lead_score}%
          </Badge>
          <span className="text-xs font-medium text-muted-foreground">{classification.label}</span>
          {lead.intent_score > 0 && (
            <Badge variant="outline" className="text-sm" title="Intent Score — вероятность скорой потребности">
              🌱 {lead.intent_score}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {formatDate(lead.created_at)}
          </span>
          <div className="w-40">
            <Select
              value={lead.status}
              disabled={updating}
              onChange={(e) =>
                onStatusChange(lead.id, e.target.value as LeadStatus)
              }
            >
              {LEAD_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s] ?? s}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {lead.summary && <p className="text-sm font-medium">{lead.summary}</p>}

        {lead.raw_text && (
          <p className="whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
            {lead.raw_text}
          </p>
        )}

        <div className="flex flex-wrap gap-1">
          {lead.services.map((s) => (
            <Badge key={s} variant="outline">
              {s}
            </Badge>
          ))}
        </div>

        {lead.positive_signals.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Почему подходит:</p>
            <ul className="space-y-0.5 text-xs text-foreground">
              {lead.positive_signals.map((signal) => (
                <li key={signal} className="flex items-start gap-1.5">
                  <span className="text-emerald-500">✓</span>
                  {signal}
                </li>
              ))}
            </ul>
          </div>
        )}

        {lead.intent_signals.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">
              Признаки скорой потребности:
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

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
          <div>
            <dt className="text-muted-foreground">Бюджет</dt>
            <dd>{formatBudget(lead.budget_min, lead.budget_max, lead.currency)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Срочность</dt>
            <dd>{lead.urgency ?? '—'}</dd>
          </div>
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
          <div>
            <dt className="text-muted-foreground">Ниша</dt>
            <dd>{lead.business_niche ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Сложность</dt>
            <dd>{lead.complexity ?? '—'}</dd>
          </div>
        </dl>

        {feedbackError && <p className="text-xs text-destructive">{feedbackError}</p>}

        <div className="flex flex-wrap items-center gap-1.5 border-t border-border pt-3">
          {lead.raw_url && (
            <a
              href={lead.raw_url}
              target="_blank"
              rel="noreferrer noopener"
              className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
            >
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
              Источник
            </a>
          )}
          <Button variant="outline" size="sm" onClick={handleCopy} disabled={!lead.raw_text}>
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            {copied ? 'Скопировано' : 'Скопировать'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleFeedback('saved')}
            disabled={feedbackBusy || feedbackDone === 'saved'}
          >
            <Bookmark className="mr-1.5 h-3.5 w-3.5" />
            {feedbackDone === 'saved' ? 'Сохранено' : 'Сохранить'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleFeedback('irrelevant')}
            disabled={feedbackBusy || feedbackDone === 'irrelevant'}
          >
            <ThumbsDown className="mr-1.5 h-3.5 w-3.5" />
            {feedbackDone === 'irrelevant' ? 'Отмечено' : 'Не подходит'}
          </Button>
          <Button variant="outline" size="sm" disabled title="AI-отклики появятся в одном из следующих обновлений">
            <MessageSquareText className="mr-1.5 h-3.5 w-3.5" />
            Откликнуться · скоро
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
