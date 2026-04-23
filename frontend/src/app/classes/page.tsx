"use client";

import { useEffect, useState } from 'react';
import { Users, Upload, FileDown, Plus, Loader2 } from 'lucide-react';
import CsvUploadModal from '@/components/CsvUploadModal';
import { api } from '@/lib/api';

type ClassRow = { id: string; name: string; student_count: number };
type ExamRow = { id: string; name: string };

export default function ClassesPage() {
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);
  const [classes, setClasses] = useState<ClassRow[]>([]);
  const [exams, setExams] = useState<ExamRow[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedExamId, setSelectedExamId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creatingClass, setCreatingClass] = useState(false);

  const load = async () => {
    setError(null);
    try {
      const [cRes, eRes] = await Promise.all([
        api.get<ClassRow[]>('/classes'),
        api.get<ExamRow[]>('/exams'),
      ]);
      setClasses(cRes.data);
      setExams(eRes.data);
      if (cRes.data.length && !selectedClassId) {
        setSelectedClassId(cRes.data[0].id);
      }
      if (eRes.data.length && !selectedExamId) {
        setSelectedExamId(eRes.data[0].id);
      }
    } catch {
      setError('Não foi possível carregar turmas ou provas. A API está rodando?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleUploadSuccess = () => {
    setIsCsvModalOpen(false);
    load();
  };

  const handleDownloadPDF = async (classIdOverride?: string) => {
    const cid = classIdOverride ?? selectedClassId;
    if (!cid || !selectedExamId) {
      setError('Selecione uma turma com alunos e uma prova.');
      return;
    }
    setError(null);
    try {
      const response = await api.get(
        `/classes/${cid}/exams/${selectedExamId}/generate-pdfs`,
        { responseType: 'blob' }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'cadernos_prova.pdf');
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch {
      setError('Falha no download. Importe alunos (CSV) para esta turma primeiro.');
    }
  };

  const handleCreateClass = async () => {
    setCreatingClass(true);
    setError(null);
    try {
      const { data } = await api.post<ClassRow>('/classes', { name: 'Nova turma' });
      await load();
      setSelectedClassId(data.id);
    } catch {
      setError('Não foi possível criar a turma.');
    } finally {
      setCreatingClass(false);
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">

      <CsvUploadModal
        isOpen={isCsvModalOpen}
        classId={selectedClassId}
        onClose={() => setIsCsvModalOpen(false)}
        onUploadSuccess={handleUploadSuccess}
      />

      <div className="flex flex-wrap justify-between items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Turmas & Alunos</h1>
          <p className="text-slate-500 mt-1">
            Gerencie estudantes e gere cadernos personalizados (QR Code).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCreateClass}
            disabled={creatingClass}
            className="btn-secondary flex items-center space-x-2"
          >
            {creatingClass ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            <span>Nova turma</span>
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Carregando...</span>
        </div>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-900/20 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      ) : null}

      <div className="glass-panel rounded-xl overflow-hidden shadow-sm">
        <div className="p-6 border-b border-surface-border flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Turma ativa</label>
            <select
              className="border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 bg-white dark:bg-slate-800 text-sm min-w-[220px]"
              value={selectedClassId}
              onChange={(e) => setSelectedClassId(e.target.value)}
            >
              {classes.length === 0 ? (
                <option value="">Nenhuma turma — crie uma ou importe CSV</option>
              ) : (
                classes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.student_count} alunos)
                  </option>
                ))
              )}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Prova para PDF</label>
            <select
              className="border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 bg-white dark:bg-slate-800 text-sm min-w-[220px]"
              value={selectedExamId}
              onChange={(e) => setSelectedExamId(e.target.value)}
            >
              {exams.length === 0 ? (
                <option value="">Nenhuma prova cadastrada</option>
              ) : (
                exams.map((ex) => (
                  <option key={ex.id} value={ex.id}>
                    {ex.name}
                  </option>
                ))
              )}
            </select>
          </div>
          <button
            type="button"
            onClick={() => void handleDownloadPDF()}
            disabled={!selectedClassId || !selectedExamId}
            className="btn-primary text-sm px-4 py-2 disabled:opacity-50"
          >
            Baixar PDF da turma
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/30 text-slate-500 text-xs uppercase tracking-wider font-semibold">
                <th className="px-6 py-4">Turma</th>
                <th className="px-6 py-4">Alunos</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {classes.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-8 text-center text-slate-500 text-sm">
                    Nenhuma turma ainda. Clique em &quot;Nova turma&quot; e importe o CSV de alunos.
                  </td>
                </tr>
              ) : (
                classes.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-3">
                        <div className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                          <Users className="w-5 h-5 text-blue-600" />
                        </div>
                        <div>
                          <div className="font-medium text-slate-800 dark:text-slate-200">{c.name}</div>
                          <div className="text-xs text-slate-500 mt-0.5 font-mono">{c.id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">{c.student_count}</td>
                    <td className="px-6 py-4">
                      <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400 text-xs font-medium rounded-full border border-emerald-200 dark:border-emerald-800">
                        Ativo
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end space-x-2">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedClassId(c.id);
                            setIsCsvModalOpen(true);
                          }}
                          className="p-2 bg-slate-100 text-slate-600 hover:text-blue-600 hover:bg-blue-50 dark:bg-slate-800 dark:hover:bg-blue-900/30 transition-colors rounded-lg flex items-center space-x-2 text-sm font-medium"
                        >
                          <Upload className="w-4 h-4" />
                          <span>CSV</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDownloadPDF(c.id)}
                          className="p-2 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-400 transition-colors rounded-lg flex items-center space-x-2 text-sm font-medium border border-emerald-200 dark:border-emerald-800"
                        >
                          <FileDown className="w-4 h-4" />
                          <span>PDF</span>
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
