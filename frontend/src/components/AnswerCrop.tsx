"use client";

import { useEffect, useState } from 'react';
import { ImageOff, Loader2, ZoomIn, ZoomOut } from 'lucide-react';
import { api } from '@/lib/api';

/**
 * Recorte da caixa de resposta, ao lado da transcrição.
 *
 * Conferir quatro palavras de cursiva olhando a imagem leva três segundos. Sem a
 * imagem o professor não tem como revisar de fato — ele aprova o que a IA
 * escreveu. Este componente existe para que a revisão seja revisão.
 *
 * A autenticação é por Bearer em localStorage, então `<img src>` direto não
 * serve: a imagem é buscada como blob e exibida por object URL.
 */
export function AnswerCrop({ scoreId }: { scoreId: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'missing'>('loading');
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    async function load() {
      setState('loading');
      try {
        const response = await api.get(`/reviews/scores/${scoreId}/crop`, {
          responseType: 'blob',
        });
        if (cancelled) return;
        objectUrl = URL.createObjectURL(response.data as Blob);
        setUrl(objectUrl);
        setState('ready');
      } catch {
        // 404 é o caso comum e esperado: provas processadas antes de os recortes
        // passarem a ser gravados em disco.
        if (!cancelled) setState('missing');
      }
    }

    void load();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [scoreId]);

  if (state === 'loading') {
    return (
      <div className="flex h-24 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-400 dark:border-slate-700 dark:bg-slate-800/50">
        <Loader2 className="h-4 w-4 animate-spin" />
      </div>
    );
  }

  if (state === 'missing' || !url) {
    return (
      <div className="flex h-24 flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-slate-300 bg-slate-50 text-xs text-slate-400 dark:border-slate-700 dark:bg-slate-800/50">
        <ImageOff className="h-4 w-4" />
        <span>Recorte indisponível para esta questão</span>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-slate-500">Manuscrito do aluno</span>
        <button
          type="button"
          onClick={() => setZoomed((current) => !current)}
          className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
          aria-label={zoomed ? 'Reduzir recorte' : 'Ampliar recorte'}
        >
          {zoomed ? <ZoomOut className="h-3.5 w-3.5" /> : <ZoomIn className="h-3.5 w-3.5" />}
          {zoomed ? 'Reduzir' : 'Ampliar'}
        </button>
      </div>
      <div className="overflow-auto rounded-lg border border-slate-200 bg-white p-1 dark:border-slate-700 dark:bg-slate-900">
        {/* eslint-disable-next-line @next/next/no-img-element -- object URL de blob autenticado */}
        <img
          src={url}
          alt="Recorte da resposta manuscrita"
          className={zoomed ? 'max-w-none' : 'w-full'}
          style={zoomed ? { width: '200%' } : undefined}
        />
      </div>
    </div>
  );
}
