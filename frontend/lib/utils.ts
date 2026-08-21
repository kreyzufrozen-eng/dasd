import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// Standard shadcn/ui `cn` helper: merges conditional class names and
// resolves Tailwind class conflicts (e.g. "p-2" vs "p-4").
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatBudget(
  min: number | null | undefined,
  max: number | null | undefined,
  currency: string | null | undefined
): string {
  const cur = currency || '';
  if (min == null && max == null) return '—';
  if (min != null && max != null && min !== max) {
    return `${min.toLocaleString('ru-RU')}–${max.toLocaleString('ru-RU')} ${cur}`.trim();
  }
  const val = (min ?? max) as number;
  return `${val.toLocaleString('ru-RU')} ${cur}`.trim();
}

export const STATUS_LABELS: Record<string, string> = {
  new: 'Новый',
  viewed: 'Просмотрен',
  contacted: 'Связались',
  interested: 'Заинтересован',
  negotiation: 'Переговоры',
  converted: 'Конвертирован',
  rejected: 'Отклонён',
  archived: 'В архиве',
};

export function scoreTier(score: number | null | undefined): 'hot' | 'warm' | 'cold' {
  const s = score ?? 0;
  if (s >= 90) return 'hot';
  if (s >= 60) return 'warm';
  return 'cold';
}

export const KEYWORD_CATEGORY_LABELS: Record<string, string> = {
  direct_intent: 'Прямое намерение',
  service: 'Услуга',
  project_type: 'Тип проекта',
  problem: 'Проблема',
  technology: 'Технология',
  hidden_intent: 'Скрытый спрос',
  exclusion: 'Исключение',
};

export interface LeadClassification {
  emoji: string;
  label: string;
  badgeVariant: 'hot' | 'warm' | 'cold';
}

// Match Score bands (see IMPLEMENTATION_PLAN.md §5) — lead_score IS the
// Match Score now that Lead is scoped per SearchProfile (Stage 1) and the
// AI prompt/scoring are profile-aware (Этап 3). intent_score is a second,
// independent axis: a message can score low on "is this a lead right now"
// but high on "will this profile's services be needed soon".
export function classifyLead(
  leadScore: number,
  intentScore: number
): LeadClassification {
  if (intentScore >= 60 && leadScore < 60) {
    return { emoji: '🟣', label: 'Скрытый спрос', badgeVariant: 'cold' };
  }
  if (leadScore >= 75) {
    return { emoji: '🔥', label: 'Горячий лид', badgeVariant: 'hot' };
  }
  if (leadScore >= 60) {
    return { emoji: '🟠', label: 'Потенциальный', badgeVariant: 'warm' };
  }
  return { emoji: '⚪', label: 'Низкая релевантность', badgeVariant: 'cold' };
}

export const BUDGET_PRESETS: { label: string; value: number | null }[] = [
  { label: 'Не учитывать бюджет', value: null },
  { label: 'От 5 000 ₽', value: 5000 },
  { label: 'От 10 000 ₽', value: 10000 },
  { label: 'От 30 000 ₽', value: 30000 },
  { label: 'От 50 000 ₽', value: 50000 },
];
