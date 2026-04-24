"use client";

import { useEffect, useState } from 'react';
import { Users, Upload, Plus, Loader2 } from 'lucide-react';
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

  const load = async () => {
    setError(null);
    try {
      const cRes = await api.get<ClassRow[]>('/classes');
      setClasses(cRes.data);
      if (cRes.data.length && !selectedClassId) {
        setSelectedClassId(cRes.data[0].id);
      }
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
            Gerencie suas turmas e importe a lista de alunos via CSV.
          </p>
        </div>
        <button
          type="button"
          onClick={handleCreateClass}
          disabled={creatingClass}
          className="btn-primary flex items-center space-x-2"
        >
          {creatingClass ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          <span>Nova turma</span>
        </button>
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
              {classes.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-6 py-8 text-center text-slate-500 text-sm">
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
                          <div className="text-xs text-slate-500 mt-0.5 font-mono">{c.id.slice(0, 8)}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">{c.student_count}</td>
                    <td className="px-6 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedClassId(c.id);
                          setIsCsvModalOpen(true);
                        }}
                        className="p-2 bg-slate-100 text-slate-600 hover:text-blue-600 hover:bg-blue-50 dark:bg-slate-800 dark:hover:bg-blue-900/30 transition-colors rounded-lg flex items-center space-x-2 text-sm font-medium ml-auto"
                      >
                        <Upload className="w-4 h-4" />
                        <span>Importar CSV</span>
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
