'use client';

import * as React from 'react';

import { ApiError, getActiveLegalDocument } from '@/lib/api';
import type { LegalDocumentRead, LegalDocumentType } from '@/lib/types';
import { formatDate } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function LegalDocumentPage({
  type,
  fallbackTitle,
}: {
  type: LegalDocumentType;
  fallbackTitle: string;
}) {
  const [doc, setDoc] = React.useState<LegalDocumentRead | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [notPublished, setNotPublished] = React.useState(false);

  React.useEffect(() => {
    setLoading(true);
    setNotPublished(false);
    getActiveLegalDocument(type)
      .then(setDoc)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) {
          setNotPublished(true);
        }
      })
      .finally(() => setLoading(false));
  }, [type]);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{doc?.title ?? fallbackTitle}</h1>
        {doc && (
          <p className="text-sm text-muted-foreground">
            Версия {doc.version}
            {doc.published_at ? ` · опубликовано ${formatDate(doc.published_at)}` : ''}
          </p>
        )}
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Загрузка…</p>
      ) : notPublished ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              Документ ещё не опубликован
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Актуальный текст появится здесь после публикации администратором сервиса.
            </p>
          </CardContent>
        </Card>
      ) : doc ? (
        <div className="prose prose-sm max-w-none whitespace-pre-wrap text-sm leading-relaxed text-foreground">
          {doc.content}
        </div>
      ) : null}
    </div>
  );
}
