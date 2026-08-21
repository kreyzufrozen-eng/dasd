'use client';

import * as React from 'react';
import { Loader2, Pencil, Plus, Sparkles, Trash2 } from 'lucide-react';

import {
  ApiError,
  createProfileKeyword,
  deleteProfileKeyword,
  generateProfileDraft,
  getProfileKeywords,
  updateProfileKeyword,
} from '@/lib/api';
import { useActiveProfile } from '@/lib/profile-context';
import { KEYWORD_CATEGORIES, type KeywordCategory, type SearchProfileKeywordRead } from '@/lib/types';
import { KEYWORD_CATEGORY_LABELS } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
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

interface KeywordForm {
  text: string;
  category: KeywordCategory;
  weight: string;
  enabled: boolean;
}

const EMPTY_FORM: KeywordForm = {
  text: '',
  category: 'service',
  weight: '1',
  enabled: true,
};

export default function KeywordsPage() {
  const { activeProfile, activeProfileId } = useActiveProfile();
  const [keywords, setKeywords] = React.useState<SearchProfileKeywordRead[]>([]);
  const [categoryFilter, setCategoryFilter] = React.useState<KeywordCategory | ''>('');
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [generating, setGenerating] = React.useState(false);

  const [addOpen, setAddOpen] = React.useState(false);
  const [addForm, setAddForm] = React.useState<KeywordForm>(EMPTY_FORM);
  const [submitting, setSubmitting] = React.useState(false);

  const [editing, setEditing] = React.useState<SearchProfileKeywordRead | null>(null);
  const [editForm, setEditForm] = React.useState<KeywordForm>(EMPTY_FORM);

  const [busyId, setBusyId] = React.useState<number | null>(null);

  const fetchKeywords = React.useCallback(() => {
    if (!activeProfileId) return;
    setLoading(true);
    setError(null);
    getProfileKeywords(activeProfileId, categoryFilter || undefined)
      .then(setKeywords)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить ключевые слова');
      })
      .finally(() => setLoading(false));
  }, [activeProfileId, categoryFilter]);

  React.useEffect(() => {
    fetchKeywords();
  }, [fetchKeywords]);

  async function handleGenerate() {
    if (!activeProfileId || !activeProfile) return;
    setGenerating(true);
    setError(null);
    const description =
      activeProfile.profession_description ||
      activeProfile.ai_profile_context ||
      `${activeProfile.profession || activeProfile.name}. Услуги: ${
        activeProfile.services.join(', ') || 'не указаны'
      }.`;
    try {
      const draft = await generateProfileDraft(description);
      const existingTexts = new Set(keywords.map((k) => k.text.toLowerCase()));
      const newOnes = draft.suggested_keywords.filter(
        (k) => !existingTexts.has(k.text.toLowerCase())
      );
      for (const kw of newOnes) {
        await createProfileKeyword(activeProfileId, {
          text: kw.text,
          category: kw.category,
          weight: kw.weight,
        });
      }
      fetchKeywords();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сгенерировать ключевые слова');
    } finally {
      setGenerating(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!activeProfileId) return;
    setSubmitting(true);
    setError(null);
    try {
      await createProfileKeyword(activeProfileId, {
        text: addForm.text,
        category: addForm.category,
        weight: Number(addForm.weight) || 1,
        enabled: addForm.enabled,
      });
      setAddOpen(false);
      setAddForm(EMPTY_FORM);
      fetchKeywords();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать ключевое слово');
    } finally {
      setSubmitting(false);
    }
  }

  function openEdit(kw: SearchProfileKeywordRead) {
    setEditing(kw);
    setEditForm({
      text: kw.text,
      category: kw.category,
      weight: String(kw.weight),
      enabled: kw.enabled,
    });
  }

  async function handleEditSave(e: React.FormEvent) {
    e.preventDefault();
    if (!editing || !activeProfileId) return;
    setSubmitting(true);
    setError(null);
    try {
      await updateProfileKeyword(activeProfileId, editing.id, {
        text: editForm.text,
        category: editForm.category,
        weight: Number(editForm.weight) || 1,
        enabled: editForm.enabled,
      });
      setEditing(null);
      fetchKeywords();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось обновить ключевое слово');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleActive(kw: SearchProfileKeywordRead) {
    if (!activeProfileId) return;
    setBusyId(kw.id);
    const prev = keywords;
    setKeywords((cur) =>
      cur.map((k) => (k.id === kw.id ? { ...k, enabled: !k.enabled } : k))
    );
    try {
      await updateProfileKeyword(activeProfileId, kw.id, { enabled: !kw.enabled });
    } catch (err) {
      setKeywords(prev);
      setError(err instanceof ApiError ? err.message : 'Не удалось обновить ключевое слово');
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(kw: SearchProfileKeywordRead) {
    if (!activeProfileId) return;
    if (!window.confirm(`Удалить ключевое слово «${kw.text}»?`)) return;
    setBusyId(kw.id);
    try {
      await deleteProfileKeyword(activeProfileId, kw.id);
      setKeywords((cur) => cur.filter((k) => k.id !== kw.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось удалить ключевое слово');
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Ключевые слова</h1>
          <p className="text-sm text-muted-foreground">
            {activeProfile
              ? `Слова и веса для поиска «${activeProfile.name}»`
              : 'Слова и веса, используемые для скоринга лидов'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleGenerate} disabled={generating}>
            {generating ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-1.5 h-4 w-4" />
            )}
            Сгенерировать ключевые слова
          </Button>
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="mr-1.5 h-4 w-4" />
            Добавить слово
          </Button>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-1">
        <Button
          size="sm"
          variant={categoryFilter === '' ? 'default' : 'outline'}
          onClick={() => setCategoryFilter('')}
        >
          Все
        </Button>
        {KEYWORD_CATEGORIES.map((c) => (
          <Button
            key={c}
            size="sm"
            variant={categoryFilter === c ? 'default' : 'outline'}
            onClick={() => setCategoryFilter(c)}
          >
            {KEYWORD_CATEGORY_LABELS[c]}
          </Button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold text-foreground">
            Все ключевые слова
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Загрузка…</p>
          ) : keywords.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Ключевые слова не найдены — добавьте вручную или нажмите «Сгенерировать ключевые слова».
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Слово</TableHead>
                  <TableHead>Категория</TableHead>
                  <TableHead>Вес</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead className="text-right">Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {keywords.map((kw) => (
                  <TableRow key={kw.id}>
                    <TableCell className="font-medium">{kw.text}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{KEYWORD_CATEGORY_LABELS[kw.category]}</Badge>
                    </TableCell>
                    <TableCell>{kw.weight}</TableCell>
                    <TableCell>
                      <button
                        onClick={() => handleToggleActive(kw)}
                        disabled={busyId === kw.id}
                        className="disabled:opacity-50"
                      >
                        <Badge variant={kw.enabled ? 'success' : 'outline'}>
                          {kw.enabled ? 'Активно' : 'Отключено'}
                        </Badge>
                      </button>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEdit(kw)}
                        aria-label="Редактировать"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={busyId === kw.id}
                        onClick={() => handleDelete(kw)}
                        aria-label="Удалить"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Add dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent onClose={() => setAddOpen(false)}>
          <DialogHeader>
            <DialogTitle>Новое ключевое слово</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Слово</label>
              <Input
                required
                value={addForm.text}
                onChange={(e) => setAddForm((f) => ({ ...f, text: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Категория</label>
              <Select
                value={addForm.category}
                onChange={(e) =>
                  setAddForm((f) => ({ ...f, category: e.target.value as KeywordCategory }))
                }
              >
                {KEYWORD_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {KEYWORD_CATEGORY_LABELS[c]}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Вес</label>
              <Input
                type="number"
                step="0.1"
                value={addForm.weight}
                onChange={(e) => setAddForm((f) => ({ ...f, weight: e.target.value }))}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={addForm.enabled}
                onChange={(e) => setAddForm((f) => ({ ...f, enabled: e.target.checked }))}
              />
              Активно
            </label>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setAddOpen(false)}>
                Отмена
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Сохранение…' : 'Создать'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent onClose={() => setEditing(null)}>
          <DialogHeader>
            <DialogTitle>Редактировать ключевое слово</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEditSave} className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Слово</label>
              <Input
                required
                value={editForm.text}
                onChange={(e) => setEditForm((f) => ({ ...f, text: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Категория</label>
              <Select
                value={editForm.category}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, category: e.target.value as KeywordCategory }))
                }
              >
                {KEYWORD_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {KEYWORD_CATEGORY_LABELS[c]}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Вес</label>
              <Input
                type="number"
                step="0.1"
                value={editForm.weight}
                onChange={(e) => setEditForm((f) => ({ ...f, weight: e.target.value }))}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={editForm.enabled}
                onChange={(e) => setEditForm((f) => ({ ...f, enabled: e.target.checked }))}
              />
              Активно
            </label>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditing(null)}>
                Отмена
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Сохранение…' : 'Сохранить'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
