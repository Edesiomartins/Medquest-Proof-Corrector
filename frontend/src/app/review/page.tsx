"use client";

import { useEffect, useState } from 'react';
import { CheckCircle, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';

type QuestionScoreDetail = {
  id: string;
  question_number: number;
  question_text: string;
  max_score: number;
  ai_score: number;
  ai_justification: string | null;
  final_score: number | null;
  professor_comment: string | null;
  extracted_answer_text: string | null;
  ocr_provider: string | null;
  ocr_confidence: number | null;
  grading_confidence: number | null;
  requires_manual_review: boolean;
  manual_review_reason: string | null;
  source_page_number: number | null;
};

type StudentResultDetail = {
  id: string;
  student_name: string | null;
  registration_number: string | null;
  page_number: number;
  total_score: number;
  status: string;
  scores: QuestionScoreDetail[];
};

function shouldDisplayAiJustification(value: string | null): boolean {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  if (!normalized) return false;
  if (normalized.startsWith('erro no processamento:')) return false;
  return true;
}

export default function ReviewPage() {
  const [result, setResult] = useState<StudentResultDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [localScores, setLocalScores] = useState<Record<string, { score: number; comment: string }>>({});

  const fetchNext = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get<StudentResultDetail>('/reviews/next');
      setResult(data);
      const initial: Record<string, { score: number; comment: string }> = {};
      for (const s of data.scores) {
        if (!s.requires_manual_review) continue;
        initial[s.id] = {
          score: s.final_score ?? s.ai_score,
          comment: s.professor_comment ?? "",
        };
      }
      setLocalScores(initial);
    } catch (err: unknown) {
      const statusCode = (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { status?: number } }).response?.status
      ) || undefined;
      if (statusCode === 404) {
        setError("Nenhuma correção pendente de revisão.");
      } else {
        setError("Erro ao carregar revisão.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchNext();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleApprove = async () => {
    if (!result) return;
    const pending = result.scores.filter((s) => s.requires_manual_review);
    if (pending.length === 0) return;

    setSaving(true);

    try {
      for (const s of pending) {
        const local = localScores[s.id];
        if (local) {
          await api.post(`/reviews/scores/${s.id}`, {
            final_score: local.score,
            professor_comment: local.comment || null,
          });
        }
      }
      await api.post(`/reviews/results/${result.id}/approve`);
      await fetchNext();
    } catch {
      setError("Erro ao salvar revisão.");
    } finally {
      setSaving(false);
    }
  };

  const updateLocal = (scoreId: string, field: "score" | "comment", value: number | string) => {
    setLocalScores((prev) => ({
      ...prev,
      [scoreId]: { ...prev[scoreId], [field]: value },
    }));
  };

  if (loading) {
    return (
      <div className="h-[calc(100vh-8rem)] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-600" />
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="h-[calc(100vh-8rem)] flex flex-col items-center justify-center space-y-4">
        <div className="bg-emerald-50 text-emerald-700 p-6 rounded-xl border border-emerald-200 flex flex-col items-center text-center">
          <CheckCircle className="w-12 h-12 mb-4" />
          <h2 className="text-xl font-bold">{error || "Tudo pronto!"}</h2>
          <p className="mt-2 text-emerald-600/80">
            {error?.includes("pendente") ? "" : "Você está em dia com as correções."}
          </p>
        </div>
        <Link href="/">
          <button className="btn-primary">Voltar para a Home</button>
        </Link>
      </div>
    );
  }

  const pendingScores = result.scores.filter((s) => s.requires_manual_review);
  const autoScores = result.scores.filter((s) => !s.requires_manual_review);

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Revisão de exceções</h1>
          <p className="text-slate-500 text-sm mt-1">
            Corrija apenas itens duvidosos; questões autoaprovadas ficam como referência abaixo.
          </p>
          <p className="text-slate-600 text-sm mt-1">
            {result.student_name
              ? `${result.student_name} (${result.registration_number})`
              : `Primeira página da prova: ${result.page_number}`}
            {" — Total: "}
            <span className="font-bold text-emerald-600">{result.total_score.toFixed(2)} pts</span>
          </p>
        </div>
        <button
          onClick={handleApprove}
          disabled={saving || pendingScores.length === 0}
          className="btn-primary flex items-center space-x-2 shadow-emerald-500/20 shadow-md disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
          <span>Confirmar pendências & próximo</span>
        </button>
      </div>

      {pendingScores.length === 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900 text-sm">
          Nenhuma questão pendente neste resultado. Use o botão para finalizar ou avance com a fila.
        </div>
      )}

      {pendingScores.map((s) => {
        const local = localScores[s.id] || {
          score: s.final_score ?? s.ai_score,
          comment: s.professor_comment ?? "",
        };
        return (
          <div key={s.id} className="glass-panel rounded-xl p-6 border border-surface-border space-y-4">
            <div className="flex justify-between items-start gap-4">
              <div>
                <h3 className="font-bold text-lg">Questão {s.question_number}</h3>
                {s.source_page_number != null && (
                  <p className="text-xs text-slate-400 mt-0.5">Página física: {s.source_page_number}</p>
                )}
                <p className="text-sm text-slate-500 mt-1">{s.question_text}</p>
              </div>
              <div className="text-right shrink-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">IA:</span>
                  <span className="text-lg font-bold text-emerald-600">{s.ai_score.toFixed(2)}</span>
                  <span className="text-slate-400">/ {s.max_score.toFixed(2)}</span>
                </div>
              </div>
            </div>

            {s.manual_review_reason && (
              <div className="bg-amber-50 dark:bg-amber-950/30 p-3 rounded-lg text-sm text-amber-900 dark:text-amber-200 border border-amber-200/80">
                <span className="font-semibold text-xs uppercase">Motivo da revisão: </span>
                {s.manual_review_reason}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 text-xs text-slate-600 dark:text-slate-400">
              <div>
                Confiança OCR:{" "}
                <span className="font-medium">
                  {s.ocr_confidence != null ? `${(s.ocr_confidence * 100).toFixed(0)}%` : "—"}
                </span>
                {s.ocr_provider ? ` (${s.ocr_provider})` : ""}
              </div>
              <div>
                Confiança IA:{" "}
                <span className="font-medium">
                  {s.grading_confidence != null ? `${(s.grading_confidence * 100).toFixed(0)}%` : "—"}
                </span>
              </div>
            </div>

            {s.extracted_answer_text && (
              <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-lg text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
                <span className="font-semibold text-xs text-slate-500 uppercase block mb-1">
                  Texto extraído
                </span>
                {s.extracted_answer_text}
              </div>
            )}

            {shouldDisplayAiJustification(s.ai_justification) && (
              <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-lg text-sm text-slate-600 dark:text-slate-400">
                <span className="font-semibold text-xs text-slate-500 uppercase">Justificativa IA: </span>
                {s.ai_justification}
              </div>
            )}

            <div className="flex items-center gap-4">
              <label className="text-sm font-medium text-slate-600">Nota final:</label>
              <input
                type="range"
                min={0}
                max={s.max_score}
                step={0.25}
                value={local.score}
                onChange={(e) => updateLocal(s.id, "score", parseFloat(e.target.value))}
                className="flex-1 accent-emerald-500"
              />
              <input
                type="number"
                step={0.25}
                min={0}
                max={s.max_score}
                value={local.score}
                onChange={(e) => updateLocal(s.id, "score", parseFloat(e.target.value) || 0)}
                className="w-20 px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-center font-bold text-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>

            <textarea
              value={local.comment}
              onChange={(e) => updateLocal(s.id, "comment", e.target.value)}
              placeholder="Comentário do professor (opcional)..."
              className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 resize-none h-16"
            />
          </div>
        );
      })}

      {autoScores.length > 0 && (
        <details className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white/40 dark:bg-slate-900/40 p-4">
          <summary className="cursor-pointer text-sm font-medium text-slate-600 dark:text-slate-300">
            Questões já autoaprovadas ({autoScores.length}) — contexto apenas
          </summary>
          <ul className="mt-3 space-y-2 text-sm text-slate-600 dark:text-slate-400">
            {autoScores.map((s) => (
              <li key={s.id}>
                Q{s.question_number}: <span className="font-semibold text-emerald-600">{(s.final_score ?? s.ai_score).toFixed(2)}</span>
                {" / "}{s.max_score.toFixed(2)}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
