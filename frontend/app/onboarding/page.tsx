'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, Plus, Sparkles, Trash2, X } from 'lucide-react';

import {
  addCustomProfileSource,
  ApiError,
  bulkAttachProfileSources,
  createSearchProfile,
  generateProfileDraft,
  getSourceCatalog,
} from '@/lib/api';
import { useActiveProfile } from '@/lib/profile-context';
import type {
  ProfileDraft,
  SourceCatalogEntry,
  SuggestedKeyword,
} from '@/lib/types';
import { BUDGET_PRESETS, KEYWORD_CATEGORY_LABELS, cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';

const TOTAL_STEPS = 7;

const SOURCE_CATEGORY_LABELS: Record<string, string> = {
  freelance: '🔥 Фриланс и заказы',
  design: '🎨 Дизайн',
  development: '💻 Разработка',
  marketing: '📈 Маркетинг',
  marketplaces: '🛒 Маркетплейсы',
  business: '💼 Бизнес',
  ai: '🤖 AI и автоматизация',
};

interface CustomSourceDraft {
  name: string;
  type: 'telegram';
  url: string;
  external_identifier: string;
}

function StepShell({
  step,
  title,
  subtitle,
  children,
  onBack,
  onNext,
  nextLabel = 'Продолжить',
  nextDisabled = false,
  nextLoading = false,
  hideNext = false,
}: {
  step: number;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  onBack?: () => void;
  onNext?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  nextLoading?: boolean;
  hideNext?: boolean;
}) {
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="flex items-center gap-1.5">
        {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
          <div
            key={i}
            className={cn(
              'h-1.5 flex-1 rounded-full',
              i < step ? 'bg-primary' : 'bg-border'
            )}
          />
        ))}
      </div>

      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>

      <div>{children}</div>

      <div className="flex items-center justify-between pt-2">
        {onBack ? (
          <Button variant="ghost" onClick={onBack} disabled={nextLoading}>
            Назад
          </Button>
        ) : (
          <span />
        )}
        {!hideNext && (
          <Button onClick={onNext} disabled={nextDisabled || nextLoading}>
            {nextLoading && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
            {nextLabel}
          </Button>
        )}
      </div>
    </div>
  );
}

function CheckList({
  items,
  selected,
  onToggle,
}: {
  items: string[];
  selected: Set<string>;
  onToggle: (item: string) => void;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">Нет предложенных вариантов.</p>;
  }
  return (
    <div className="space-y-1.5">
      {items.map((item) => (
        <label
          key={item}
          className="flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
        >
          <input
            type="checkbox"
            checked={selected.has(item)}
            onChange={() => onToggle(item)}
            className="h-4 w-4"
          />
          {item}
        </label>
      ))}
    </div>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const { refresh: refreshProfiles } = useActiveProfile();

  const [step, setStep] = React.useState(1);
  const [error, setError] = React.useState<string | null>(null);

  // Step 1
  const [description, setDescription] = React.useState('');
  const [draftLoading, setDraftLoading] = React.useState(false);
  const [draft, setDraft] = React.useState<ProfileDraft | null>(null);

  // Editable, seeded from the draft once it arrives
  const [profession, setProfession] = React.useState('');
  const [services, setServices] = React.useState<string[]>([]);
  const [newService, setNewService] = React.useState('');

  // Step 2
  const [selectedOrders, setSelectedOrders] = React.useState<Set<string>>(new Set());
  const [contextText, setContextText] = React.useState('');

  // Step 3
  const [selectedExclusions, setSelectedExclusions] = React.useState<Set<string>>(new Set());
  const [customExclusion, setCustomExclusion] = React.useState('');

  // Step 4
  const [minBudget, setMinBudget] = React.useState<number | null>(null);
  const [customBudget, setCustomBudget] = React.useState('');

  // Step 5
  const [keywords, setKeywords] = React.useState<SuggestedKeyword[]>([]);
  const [newKeywordText, setNewKeywordText] = React.useState('');
  const [newKeywordCategory, setNewKeywordCategory] = React.useState('direct_intent');
  const [regenerating, setRegenerating] = React.useState(false);

  // Step 6
  const [catalog, setCatalog] = React.useState<SourceCatalogEntry[]>([]);
  const [catalogLoading, setCatalogLoading] = React.useState(false);
  const [selectedSourceIds, setSelectedSourceIds] = React.useState<Set<number>>(new Set());
  const [customSources, setCustomSources] = React.useState<CustomSourceDraft[]>([]);
  const [addingSource, setAddingSource] = React.useState(false);
  const [newSourceUrl, setNewSourceUrl] = React.useState('');

  // Step 7
  const [launching, setLaunching] = React.useState(false);

  function applyDraft(d: ProfileDraft) {
    setDraft(d);
    setProfession(d.profession);
    setServices(d.services);
    setSelectedOrders(new Set(d.suggested_orders));
    setContextText(d.ai_profile_context);
    setSelectedExclusions(new Set(d.suggested_exclusions));
    setKeywords(d.suggested_keywords);
  }

  async function handleAnalyze() {
    setDraftLoading(true);
    setError(null);
    try {
      const result = await generateProfileDraft(description);
      applyDraft(result);
      setStep(2);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось проанализировать описание');
    } finally {
      setDraftLoading(false);
    }
  }

  async function handleRegenerateKeywords() {
    setRegenerating(true);
    setError(null);
    try {
      const result = await generateProfileDraft(description);
      setKeywords(result.suggested_keywords);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сгенерировать ключевые слова');
    } finally {
      setRegenerating(false);
    }
  }

  React.useEffect(() => {
    if (step !== 6 || catalog.length > 0) return;
    setCatalogLoading(true);
    getSourceCatalog()
      .then((entries) => {
        setCatalog(entries);
        // Uncategorized sources have no recognizable name for the user to
        // judge individually (see the step-6 render below) — default them
        // all to selected so a fresh search has real source coverage from
        // the start, rather than launching with zero sources attached.
        const otherIds = entries
          .filter((s) => !s.category || !SOURCE_CATEGORY_LABELS[s.category])
          .map((s) => s.id);
        if (otherIds.length > 0) {
          setSelectedSourceIds((cur) => new Set([...Array.from(cur), ...otherIds]));
        }
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить источники');
      })
      .finally(() => setCatalogLoading(false));
  }, [step, catalog.length]);

  function toggleSet<T>(set: Set<T>, value: T): Set<T> {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  }

  function addCustomSourceDraft() {
    const url = newSourceUrl.trim();
    if (!url) return;
    const identifier = url.replace(/^https?:\/\/t\.me\//i, '').replace(/^@/, '');
    setCustomSources((cur) => [
      ...cur,
      { name: identifier || url, type: 'telegram', url, external_identifier: identifier },
    ]);
    setNewSourceUrl('');
    setAddingSource(false);
  }

  async function handleLaunch() {
    setLaunching(true);
    setError(null);
    try {
      const finalBudget =
        minBudget === -1 ? Number(customBudget) || null : minBudget;

      const profile = await createSearchProfile({
        name: profession || 'Мой поиск',
        profession,
        profession_description: description,
        services,
        excluded_niches: Array.from(selectedExclusions),
        min_budget: finalBudget,
        ai_profile_context: contextText,
        keywords: keywords.map((k) => ({
          text: k.text,
          category: k.category,
          weight: k.weight,
        })),
      });

      // One request for however many catalog sources were selected
      // (the "наша база источников" bulk-select can be a few hundred) —
      // used to be one sequential await per source, which took 1-2+
      // minutes for a large selection. Custom (user-typed) sources are
      // few enough that the old per-item loop is still fine there.
      if (selectedSourceIds.size > 0) {
        try {
          await bulkAttachProfileSources(profile.id, Array.from(selectedSourceIds));
        } catch {
          // Non-fatal — the user can add sources again from Источники
          // afterwards.
        }
      }
      for (const custom of customSources) {
        try {
          await addCustomProfileSource(profile.id, custom);
        } catch {
          // Same as above.
        }
      }

      // AuthGate redirects back into /onboarding whenever the active-
      // profile list is empty — without this refresh it would still be
      // holding the pre-launch (empty) list and immediately bounce the
      // user right back here instead of landing on the Dashboard.
      await refreshProfiles();
      router.push('/');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось запустить поиск');
      setLaunching(false);
    }
  }

  const errorBanner = error && (
    <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
      {error}
    </p>
  );

  if (step === 1) {
    return (
      <StepShell
        step={1}
        title="Настроим поиск клиентов"
        subtitle="Расскажите, чем вы занимаетесь и какие заказы хотите получать. AI настроит поиск под вас."
        onNext={handleAnalyze}
        nextLabel="Продолжить"
        nextDisabled={description.trim().length < 10}
        nextLoading={draftLoading}
      >
        <div className="space-y-3">
          {errorBanner}
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={7}
            placeholder={
              'Например:\nЯ занимаюсь дизайном карточек товаров для Wildberries и Ozon.\nДелаю инфографику, Rich-контент и оформление товаров.'
            }
            className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
        </div>
      </StepShell>
    );
  }

  if (step === 2) {
    return (
      <StepShell
        step={2}
        title="Ваша специализация"
        subtitle="AI проанализировал описание — проверьте и при необходимости отредактируйте."
        onBack={() => setStep(1)}
        onNext={() => setStep(3)}
      >
        <div className="space-y-4">
          {errorBanner}
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Специализация</label>
            <Input value={profession} onChange={(e) => setProfession(e.target.value)} />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Услуги</label>
            <div className="flex flex-wrap gap-1.5">
              {services.map((s) => (
                <Badge key={s} variant="outline" className="gap-1 pr-1">
                  {s}
                  <button
                    onClick={() => setServices((cur) => cur.filter((x) => x !== s))}
                    className="rounded-full p-0.5 hover:bg-accent"
                    aria-label={`Удалить ${s}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={newService}
                onChange={(e) => setNewService(e.target.value)}
                placeholder="Добавить услугу"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newService.trim()) {
                    e.preventDefault();
                    setServices((cur) => [...cur, newService.trim()]);
                    setNewService('');
                  }
                }}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  if (newService.trim()) {
                    setServices((cur) => [...cur, newService.trim()]);
                    setNewService('');
                  }
                }}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Какие заказы вы хотите получать?</label>
            <CheckList
              items={draft?.suggested_orders ?? []}
              selected={selectedOrders}
              onToggle={(item) => setSelectedOrders((cur) => toggleSet(cur, item))}
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">
              Опишите своими словами, какие заявки вы хотите получать
            </label>
            <textarea
              value={contextText}
              onChange={(e) => setContextText(e.target.value)}
              rows={4}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
        </div>
      </StepShell>
    );
  }

  if (step === 3) {
    return (
      <StepShell
        step={3}
        title="Что не показывать?"
        subtitle="Уберите то, что вам не интересно — AI уже предложил типичные исключения для вашей сферы."
        onBack={() => setStep(2)}
        onNext={() => setStep(4)}
      >
        <div className="space-y-3">
          {errorBanner}
          <CheckList
            items={draft?.suggested_exclusions ?? []}
            selected={selectedExclusions}
            onToggle={(item) => setSelectedExclusions((cur) => toggleSet(cur, item))}
          />
          <div className="flex gap-2">
            <Input
              value={customExclusion}
              onChange={(e) => setCustomExclusion(e.target.value)}
              placeholder="Своё исключение"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && customExclusion.trim()) {
                  e.preventDefault();
                  setSelectedExclusions((cur) => new Set(cur).add(customExclusion.trim()));
                  setCustomExclusion('');
                }
              }}
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (customExclusion.trim()) {
                  setSelectedExclusions((cur) => new Set(cur).add(customExclusion.trim()));
                  setCustomExclusion('');
                }
              }}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </StepShell>
    );
  }

  if (step === 4) {
    return (
      <StepShell
        step={4}
        title="Минимальный бюджет заказа"
        onBack={() => setStep(3)}
        onNext={() => setStep(5)}
      >
        <div className="space-y-2">
          {errorBanner}
          {BUDGET_PRESETS.map((preset) => (
            <button
              key={preset.label}
              onClick={() => setMinBudget(preset.value)}
              className={cn(
                'flex w-full items-center rounded-md border px-3 py-2 text-left text-sm transition-colors',
                minBudget === preset.value && minBudget !== -1
                  ? 'border-primary bg-accent'
                  : 'border-border hover:bg-accent'
              )}
            >
              {preset.label}
            </button>
          ))}
          <button
            onClick={() => setMinBudget(-1)}
            className={cn(
              'flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors',
              minBudget === -1 ? 'border-primary bg-accent' : 'border-border hover:bg-accent'
            )}
          >
            <span className="shrink-0">Свой бюджет:</span>
            <Input
              type="number"
              min={0}
              value={customBudget}
              onChange={(e) => {
                setCustomBudget(e.target.value);
                setMinBudget(-1);
              }}
              onClick={(e) => e.stopPropagation()}
              placeholder="0"
              className="h-7"
            />
          </button>
        </div>
      </StepShell>
    );
  }

  if (step === 5) {
    const byCategory = keywords.reduce<Record<string, SuggestedKeyword[]>>((acc, kw) => {
      (acc[kw.category] ||= []).push(kw);
      return acc;
    }, {});

    return (
      <StepShell
        step={5}
        title="Ключевые слова"
        subtitle="AI сгенерировал стартовый набор — отредактируйте по своему усмотрению."
        onBack={() => setStep(4)}
        onNext={() => setStep(6)}
      >
        <div className="space-y-4">
          {errorBanner}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleRegenerateKeywords}
            disabled={regenerating}
          >
            {regenerating ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-1.5 h-4 w-4" />
            )}
            Сгенерировать ключевые слова
          </Button>

          {Object.entries(byCategory).map(([category, items]) => (
            <div key={category} className="space-y-1.5">
              <label className="text-xs text-muted-foreground">
                {KEYWORD_CATEGORY_LABELS[category] ?? category}
              </label>
              <div className="flex flex-wrap gap-1.5">
                {items.map((kw) => (
                  <Badge key={kw.text} variant="outline" className="gap-1 pr-1">
                    {kw.text}
                    <button
                      onClick={() =>
                        setKeywords((cur) => cur.filter((k) => k.text !== kw.text))
                      }
                      className="rounded-full p-0.5 hover:bg-accent"
                      aria-label={`Удалить ${kw.text}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            </div>
          ))}

          <div className="flex gap-2">
            <Input
              value={newKeywordText}
              onChange={(e) => setNewKeywordText(e.target.value)}
              placeholder="Новое ключевое слово"
            />
            <Select
              value={newKeywordCategory}
              onChange={(e) => setNewKeywordCategory(e.target.value)}
              className="w-48"
            >
              {Object.entries(KEYWORD_CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (newKeywordText.trim()) {
                  setKeywords((cur) => [
                    ...cur,
                    { text: newKeywordText.trim(), category: newKeywordCategory as SuggestedKeyword['category'], weight: 1.0 },
                  ]);
                  setNewKeywordText('');
                }
              }}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </StepShell>
    );
  }

  if (step === 6) {
    // Only categories with a real, human-recognizable label (see
    // SOURCE_CATEGORY_LABELS) get shown as an individually-pickable list —
    // most catalog rows have no category set yet (admin curation is still
    // pending), and showing a wall of unrecognizable channel usernames for
    // those is worse than useless. That bucket becomes a single "use our
    // whole database" summary card instead (below).
    const namedCategories = catalog.reduce<Record<string, SourceCatalogEntry[]>>((acc, s) => {
      if (!s.category || !SOURCE_CATEGORY_LABELS[s.category]) return acc;
      (acc[s.category] ||= []).push(s);
      return acc;
    }, {});
    const otherSources = catalog.filter(
      (s) => !s.category || !SOURCE_CATEGORY_LABELS[s.category]
    );
    const allOtherSelected =
      otherSources.length > 0 && otherSources.every((s) => selectedSourceIds.has(s.id));

    return (
      <StepShell
        step={6}
        title="Где искать клиентов?"
        subtitle="Выберите источники из каталога или добавьте свои Telegram-чаты и каналы."
        onBack={() => setStep(5)}
        onNext={() => setStep(7)}
      >
        <div className="space-y-4">
          {errorBanner}
          {catalogLoading && <p className="text-sm text-muted-foreground">Загрузка…</p>}

          {!catalogLoading && catalog.length === 0 && customSources.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Каталог источников пока пуст — добавьте свои чаты и каналы вручную ниже.
            </p>
          )}

          {Object.entries(namedCategories).map(([category, items]) => (
            <div key={category} className="space-y-1.5">
              <label className="text-xs text-muted-foreground">
                {SOURCE_CATEGORY_LABELS[category] ?? category}
              </label>
              <div className="space-y-1">
                {items.map((s) => (
                  <label
                    key={s.id}
                    className="flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
                  >
                    <input
                      type="checkbox"
                      checked={selectedSourceIds.has(s.id)}
                      onChange={() =>
                        setSelectedSourceIds((cur) => toggleSet(cur, s.id))
                      }
                      className="h-4 w-4"
                    />
                    {s.name}
                  </label>
                ))}
              </div>
            </div>
          ))}

          {otherSources.length > 0 && (
            <label className="flex cursor-pointer items-start gap-3 rounded-md border border-border px-3 py-3 text-sm hover:bg-accent">
              <input
                type="checkbox"
                checked={allOtherSelected}
                onChange={() =>
                  setSelectedSourceIds((cur) => {
                    const next = new Set(cur);
                    if (allOtherSelected) {
                      otherSources.forEach((s) => next.delete(s.id));
                    } else {
                      otherSources.forEach((s) => next.add(s.id));
                    }
                    return next;
                  })
                }
                className="mt-0.5 h-4 w-4"
              />
              <span>
                <span className="block font-medium text-foreground">
                  📡 Наша база источников — {otherSources.length} каналов
                </span>
                <span className="block text-xs text-muted-foreground">
                  Подключим все сразу — лишние можно будет отключить позже в разделе
                  «Источники».
                </span>
              </span>
            </label>
          )}

          {customSources.length > 0 && (
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Ваши источники</label>
              <div className="space-y-1">
                {customSources.map((s, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
                  >
                    {s.url}
                    <button
                      onClick={() => setCustomSources((cur) => cur.filter((_, idx) => idx !== i))}
                      className="text-muted-foreground hover:text-destructive"
                      aria-label="Удалить источник"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {addingSource ? (
            <div className="flex gap-2">
              <Input
                value={newSourceUrl}
                onChange={(e) => setNewSourceUrl(e.target.value)}
                placeholder="https://t.me/example"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') addCustomSourceDraft();
                }}
              />
              <Button type="button" onClick={addCustomSourceDraft}>
                Добавить
              </Button>
              <Button type="button" variant="ghost" onClick={() => setAddingSource(false)}>
                Отмена
              </Button>
            </div>
          ) : (
            <Button type="button" variant="outline" onClick={() => setAddingSource(true)}>
              <Plus className="mr-1.5 h-4 w-4" />
              Добавить источник
            </Button>
          )}
        </div>
      </StepShell>
    );
  }

  // step === 7
  return (
    <StepShell
      step={7}
      title="🤖 Вот что я буду искать"
      onBack={() => setStep(6)}
      onNext={handleLaunch}
      nextLabel="🚀 Запустить поиск"
      nextLoading={launching}
      hideNext={false}
    >
      <div className="space-y-4">
        {errorBanner}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-foreground">
              Ваша специализация: {profession}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <p className="font-medium text-foreground">🔥 Прямые заявки</p>
              <p className="text-muted-foreground">{draft?.summary_direct}</p>
            </div>
            <div>
              <p className="font-medium text-foreground">🟠 Потенциальные заявки</p>
              <p className="text-muted-foreground">{draft?.summary_potential}</p>
            </div>
            <div>
              <p className="font-medium text-foreground">🟣 Скрытый спрос</p>
              <p className="text-muted-foreground">{draft?.summary_hidden}</p>
            </div>
            <div>
              <p className="font-medium text-foreground">Не буду показывать</p>
              <p className="text-muted-foreground">{draft?.summary_excluded}</p>
            </div>
          </CardContent>
        </Card>
        <p className="text-xs text-muted-foreground">
          {keywords.length} ключевых слов · {selectedSourceIds.size + customSources.length} источников
        </p>
        {launching && (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Настраиваем поиск — обычно занимает несколько секунд, при большом числе
            источников может занять 1–2 минуты. Не закрывайте страницу.
          </p>
        )}
      </div>
    </StepShell>
  );
}
