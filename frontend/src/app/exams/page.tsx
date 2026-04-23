"use client";

import { useEffect, useState } from 'react';
import { Plus, BookOpen, Settings2, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';

type ExamSummary = {
  id: string;
  name: string;
  max_score: number;
  question_count: number;
};

export default function ExamsPage() {
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get<ExamSummary[]>('/exams');
        if (!cancelled) setExams(data);
      } catch {
        if (!cancelled) setError('Não foi possível carregar as provas.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Provas & Templates</h1>
          <p className="text-slate-500 mt-1">Gabaritos e rubricas para correção assistida.</p>
        </div>
        <Link href="/exams/new">
          <button type="button" className="btn-primary flex items-center space-x-2 shadow-emerald-500/20 shadow-lg">
            <Plus className="w-5 h-5" />
            <span>Criar Nova Prova</span>
          </button>
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Carregando...</span>
        </div>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      ) : null}

      <div className="glass-panel rounded-xl overflow-hidden shadow-sm mt-8">
        <div className="p-6 border-b border-surface-border">
          <h3 className="text-lg font-bold">Provas cadastradas</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/30 text-slate-500 text-xs uppercase tracking-wider font-semibold">
                <th className="px-6 py-4">Nome</th>
                <th className="px-6 py-4">Questões</th>
                <th className="px-6 py-4">Nota máx.</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {exams.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-500 text-sm">
                    Nenhuma prova ainda. Clique em &quot;Criar Nova Prova&quot;.
                  </td>
                </tr>
              ) : (
                exams.map((ex) => (
                  <tr key={ex.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-3">
                        <div className="p-2 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg">
                          <BookOpen className="w-5 h-5 text-emerald-600" />
                        </div>
                        <div>
                          <div className="font-medium text-slate-800 dark:text-slate-200">{ex.name}</div>
                          <div className="text-xs text-slate-500 mt-0.5 font-mono">{ex.id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">{ex.question_count}</td>
                    <td className="px-6 py-4 text-sm font-medium text-slate-700">{ex.max_score}</td>
                    <td className="px-6 py-4">
                      <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400 text-xs font-medium rounded-full border border-emerald-200 dark:border-emerald-800">
                        Ativo
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button type="button" className="p-2 text-slate-400 hover:text-emerald-600 transition-colors" aria-label="Configurações">
                        <Settings2 className="w-5 h-5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
