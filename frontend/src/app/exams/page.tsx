"use client";

import { useEffect, useState } from 'react';
import { Plus, BookOpen, FileDown, Loader2, Pencil, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';

type ExamSummary = {
  id: string;
  name: string;
  class_id: string | null;
  question_count: number;
};

export default function ExamsPage() {
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const loadExams = async () => {
    setError(null);
    try {
      const { data } = await api.get<ExamSummary[]>('/exams');
      setExams(data);
    } catch {
      setError('Não foi possível carregar as provas.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadExams(); }, []);

  const handleDownloadSheets = async (examId: string, examName: string) => {
    setDownloadingId(examId);
    setError(null);
    try {
      const response = await api.get(`/exams/${examId}/answer-sheets`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `folhas_${examName}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      let msg = 'Erro ao gerar folhas-resposta.';
      if (err && typeof err === 'object' && 'response' in err) {
        const resp = (err as { response?: { data?: Blob } }).response;
        if (resp?.data instanceof Blob) {
          try {
            const text = await resp.data.text();
            const json = JSON.parse(text);
            if (json.detail) msg = json.detail;
          } catch { /* keep default msg */ }
        }
      }
      setError(msg);
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDelete = async (examId: string, examName: string) => {
    if (!confirm(`Excluir a prova "${examName}" e todas as suas questões?`)) return;
    setDeletingId(examId);
    setError(null);
    try {
      await api.delete(`/exams/${examId}`);
      setExams((prev) => prev.filter((e) => e.id !== examId));
    } catch {
      setError('Erro ao excluir a prova.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Provas</h1>
          <p className="text-slate-500 mt-1">Gabaritos e questões para correção assistida.</p>
        </div>
        <Link href="/exams/new">
          <button type="button" className="btn-primary flex items-center space-x-2 shadow-emerald-500/20 shadow-lg">
            <Plus className="w-5 h-5" />
            <span>Criar Nova Prova</span>
          </button>
        </Link>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Carregando...</span>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="glass-panel rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/30 text-slate-500 text-xs uppercase tracking-wider font-semibold">
                <th className="px-6 py-4">Prova</th>
                <th className="px-6 py-4">Questões</th>
                <th className="px-6 py-4">Turma</th>
                <th className="px-6 py-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {exams.length === 0 && !loading ? (
                <tr>
                  <td colSpan={4} className="px-6 py-8 text-center text-slate-500 text-sm">
                    Nenhuma prova. Clique em &quot;Criar Nova Prova&quot;.
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
                        <div className="font-medium text-slate-800 dark:text-slate-200">{ex.name}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">{ex.question_count}</td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      {ex.class_id ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400">
                          Vinculada
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
                          Sem turma
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => handleDownloadSheets(ex.id, ex.name)}
                          disabled={!ex.class_id || ex.question_count === 0 || downloadingId === ex.id}
                          className="p-2 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-400 transition-colors rounded-lg inline-flex items-center space-x-1.5 text-xs font-medium border border-emerald-200 dark:border-emerald-800 disabled:opacity-40 disabled:cursor-not-allowed"
                          title={!ex.class_id ? "Vincule a prova a uma turma primeiro" : ex.question_count === 0 ? "Adicione questões primeiro" : "Baixar folhas-resposta"}
                        >
                          {downloadingId === ex.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />}
                          <span>Folhas</span>
                        </button>

                        <Link href={`/exams/${ex.id}/edit`}>
                          <button
                            type="button"
                            className="p-2 bg-slate-100 text-slate-600 hover:text-blue-600 hover:bg-blue-50 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-blue-900/30 transition-colors rounded-lg inline-flex items-center space-x-1.5 text-xs font-medium border border-slate-200 dark:border-slate-700"
                            title="Editar prova"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                            <span>Editar</span>
                          </button>
                        </Link>

                        <button
                          type="button"
                          onClick={() => handleDelete(ex.id, ex.name)}
                          disabled={deletingId === ex.id}
                          className="p-2 bg-red-50 text-red-600 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 transition-colors rounded-lg inline-flex items-center space-x-1.5 text-xs font-medium border border-red-200 dark:border-red-800 disabled:opacity-40"
                          title="Excluir prova"
                        >
                          {deletingId === ex.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                          <span>Excluir</span>
                        </button>
                      </div>
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
