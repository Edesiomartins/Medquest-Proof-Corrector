"use client";

import { useEffect, useState } from 'react';
import { ArrowLeft, Users, Trash2, Loader2, Save, Upload, Pencil, X, Check } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import CsvUploadModal from '@/components/CsvUploadModal';
import { api } from '@/lib/api';

type ClassData = { id: string; name: string; student_count: number };
type StudentRow = { id: string; name: string; registration_number: string; curso: string | null };

export default function ClassDetailPage() {
  const params = useParams();
  const classId = params.id as string;

  const [classData, setClassData] = useState<ClassData | null>(null);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [editingName, setEditingName] = useState(false);
  const [newName, setNewName] = useState("");
  const [savingName, setSavingName] = useState(false);

  const [deletingStudentId, setDeletingStudentId] = useState<string | null>(null);

  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);

  const loadData = async () => {
    setError(null);
    try {
      const [classRes, studentsRes] = await Promise.all([
        api.get<ClassData>(`/classes/${classId}`),
        api.get<StudentRow[]>(`/classes/${classId}/students`),
      ]);
      setClassData(classRes.data);
      setStudents(studentsRes.data);
      setNewName(classRes.data.name);
    } catch {
      setError("Não foi possível carregar a turma.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [classId]);

  const handleSaveName = async () => {
    if (!newName.trim()) return;
    setSavingName(true);
    setError(null);
    try {
      const { data } = await api.put<ClassData>(`/classes/${classId}`, { name: newName.trim() });
      setClassData(data);
      setEditingName(false);
      setSuccess("Nome da turma atualizado.");
      setTimeout(() => setSuccess(null), 3000);
    } catch {
      setError("Erro ao salvar nome da turma.");
    } finally {
      setSavingName(false);
    }
  };

  const handleDeleteStudent = async (studentId: string, studentName: string) => {
    if (!confirm(`Remover o aluno "${studentName}" da turma?`)) return;
    setDeletingStudentId(studentId);
    setError(null);
    try {
      await api.delete(`/classes/${classId}/students/${studentId}`);
      setStudents((prev) => prev.filter((s) => s.id !== studentId));
      setClassData((prev) => prev ? { ...prev, student_count: prev.student_count - 1 } : prev);
    } catch {
      setError("Erro ao remover aluno.");
    } finally {
      setDeletingStudentId(null);
    }
  };

  const handleCsvUploadSuccess = () => {
    setIsCsvModalOpen(false);
    loadData();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 gap-2 text-slate-500">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span>Carregando turma...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">

      <CsvUploadModal
        isOpen={isCsvModalOpen}
        classId={classId}
        onClose={() => setIsCsvModalOpen(false)}
        onUploadSuccess={handleCsvUploadSuccess}
      />

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href="/classes">
            <button type="button" className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
              <ArrowLeft className="w-5 h-5 text-slate-500" />
            </button>
          </Link>
          <div>
            {editingName ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSaveName()}
                  className="text-2xl font-bold bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={handleSaveName}
                  disabled={savingName}
                  className="p-1.5 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 rounded-lg transition-colors"
                  title="Salvar"
                >
                  {savingName ? <Loader2 className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
                </button>
                <button
                  type="button"
                  onClick={() => { setEditingName(false); setNewName(classData?.name || ""); }}
                  className="p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
                  title="Cancelar"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h1 className="text-3xl font-bold tracking-tight">{classData?.name}</h1>
                <button
                  type="button"
                  onClick={() => setEditingName(true)}
                  className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
                  title="Editar nome"
                >
                  <Pencil className="w-4 h-4" />
                </button>
              </div>
            )}
            <p className="text-slate-500 mt-1">
              {classData?.student_count} aluno{classData?.student_count !== 1 ? "s" : ""} cadastrado{classData?.student_count !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setIsCsvModalOpen(true)}
          className="btn-primary flex items-center space-x-2"
        >
          <Upload className="w-4 h-4" />
          <span>Importar CSV</span>
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {success && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 dark:bg-emerald-900/20 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
          {success}
        </div>
      )}

      <div className="glass-panel rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/30 text-slate-500 text-xs uppercase tracking-wider font-semibold">
                <th className="px-6 py-4">Matrícula</th>
                <th className="px-6 py-4">Nome</th>
                <th className="px-6 py-4">Turma</th>
                <th className="px-6 py-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {students.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-8 text-center text-slate-500 text-sm">
                    Nenhum aluno nesta turma. Importe um CSV para adicionar alunos.
                  </td>
                </tr>
              ) : (
                students.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-colors">
                    <td className="px-6 py-4">
                      <span className="font-mono text-sm text-slate-700 dark:text-slate-300">
                        {s.registration_number}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-700 dark:text-blue-400 text-sm font-semibold">
                          {s.name.charAt(0).toUpperCase()}
                        </div>
                        <span className="font-medium text-slate-800 dark:text-slate-200">{s.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-400">
                      {s.curso || "—"}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleDeleteStudent(s.id, s.name)}
                        disabled={deletingStudentId === s.id}
                        className="p-2 bg-red-50 text-red-600 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 transition-colors rounded-lg inline-flex items-center space-x-1.5 text-xs font-medium border border-red-200 dark:border-red-800 disabled:opacity-40"
                        title="Remover aluno"
                      >
                        {deletingStudentId === s.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                        <span>Remover</span>
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
