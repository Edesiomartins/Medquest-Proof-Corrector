"use client";

import { useEffect, useState } from 'react';
import { Users, Upload, Plus, Loader2, FileDown, Eye, Trash2, Pencil } from 'lucide-react';
import Link from 'next/link';
import CsvUploadModal from '@/components/CsvUploadModal';
import { api } from '@/lib/api';

type ClassRow = { id: string; name: string; student_count: number };

export default function ClassesPage() {
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);
  const [classes, setClasses] = useState<ClassRow[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creatingClass, setCreatingClass] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [newClassName, setNewClassName] = useState("");
  const [showNewClassInput, setShowNewClassInput] = useState(false);

  const load = async () => {
    setError(null);
    try {
      const cRes = await api.get<ClassRow[]>('/classes');
      setClasses(cRes.data);
    } catch {
      setError('Não foi possível carregar turmas. A API está rodando?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleUploadSuccess = () => {
    setIsCsvModalOpen(false);
    load();
  };

  const handleCreateClass = async () => {
    if (!newClassName.trim()) {
      setError("Digite o nome da turma.");
      return;
    }
    setCreatingClass(true);
    setError(null);
    try {
      await api.post<ClassRow>('/classes', { name: newClassName.trim() });
      setNewClassName("");
      setShowNewClassInput(false);
      await load();
    } catch {
      setError('Não foi possível criar a turma.');
    } finally {
      setCreatingClass(false);
    }
  };

  const handleDelete = async (classId: string, className: string, studentCount: number) => {
    const msg = studentCount > 0
      ? `Excluir a turma "${className}" e seus ${studentCount} aluno(s)?`
      : `Excluir a turma "${className}"?`;
    if (!confirm(msg)) return;
    setDeletingId(classId);
    setError(null);
    try {
      await api.delete(`/classes/${classId}`);
      setClasses((prev) => prev.filter((c) => c.id !== classId));
    } catch {
      setError('Erro ao excluir a turma.');
    } finally {
      setDeletingId(null);
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
            Gerencie suas turmas e importe a lista de alunos via CSV.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              const bom = "\uFEFF";
              const csv = bom + "Matrícula;Nome;Turma\n2024001;Maria Silva;Turma A\n2024002;João Santos;Turma B\n";
              const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = "modelo_alunos.csv";
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="btn-secondary flex items-center space-x-2"
          >
            <FileDown className="w-4 h-4" />
            <span>Modelo CSV</span>
          </button>
          <button
            type="button"
            onClick={() => setShowNewClassInput(true)}
            className="btn-primary flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>Nova turma</span>
          </button>
        </div>
      </div>

      {showNewClassInput && (
        <div className="glass-panel rounded-xl p-4 border border-surface-border flex items-center gap-3">
          <input
            type="text"
            value={newClassName}
            onChange={(e) => setNewClassName(e.target.value)}
            placeholder="Nome da turma (ex: Medicina 2025.1)"
            className="flex-1 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
            onKeyDown={(e) => e.key === 'Enter' && handleCreateClass()}
            autoFocus
          />
          <button
            type="button"
            onClick={handleCreateClass}
            disabled={creatingClass}
            className="btn-primary flex items-center space-x-2 whitespace-nowrap"
          >
            {creatingClass ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            <span>Criar</span>
          </button>
          <button
            type="button"
            onClick={() => { setShowNewClassInput(false); setNewClassName(""); }}
            className="btn-secondary px-3 py-2 text-sm"
          >
            Cancelar
          </button>
        </div>
      )}

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
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/30 text-slate-500 text-xs uppercase tracking-wider font-semibold">
                <th className="px-6 py-4">Turma</th>
                <th className="px-6 py-4">Alunos</th>
                <th className="px-6 py-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {classes.length === 0 && !loading ? (
                <tr>
                  <td colSpan={3} className="px-6 py-8 text-center text-slate-500 text-sm">
                    Nenhuma turma ainda. Clique em &quot;Nova turma&quot; para começar.
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
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400">
                        {c.student_count} aluno{c.student_count !== 1 ? "s" : ""}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link href={`/classes/${c.id}`}>
                          <button
                            type="button"
                            className="p-2 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400 transition-colors rounded-lg inline-flex items-center space-x-1.5 text-xs font-medium border border-blue-200 dark:border-blue-800"
                            title="Ver alunos"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>Ver</span>
                          </button>
                        </Link>

                        <button
                          type="button"
                          onClick={() => {
                            setSelectedClassId(c.id);
                            setIsCsvModalOpen(true);
                          }}
                          className="p-2 bg-slate-100 text-slate-600 hover:text-blue-600 hover:bg-blue-50 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-blue-900/30 transition-colors rounded-lg inline-flex items-center space-x-1.5 text-xs font-medium border border-slate-200 dark:border-slate-700"
                          title="Importar CSV"
                        >
                          <Upload className="w-3.5 h-3.5" />
                          <span>CSV</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleDelete(c.id, c.name, c.student_count)}
                          disabled={deletingId === c.id}
                          className="p-2 bg-red-50 text-red-600 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 transition-colors rounded-lg inline-flex items-center space-x-1.5 text-xs font-medium border border-red-200 dark:border-red-800 disabled:opacity-40"
                          title="Excluir turma"
                        >
                          {deletingId === c.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
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
