"use client";

import { useState } from 'react';
import { UploadCloud, CheckCircle, Clock, BarChart3, FileText } from 'lucide-react';
import Link from 'next/link';
import UploadModal from '@/components/UploadModal';

export default function Dashboard() {
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  const handleUploadSuccess = () => {
    alert("Lote recebido com sucesso pelo FastAPI! Ele já está processando os PDFs no background.");
    setIsUploadModalOpen(false);
    // TODO: Disparar reload na listagem de Lotes Recentes
  };

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      <UploadModal 
        isOpen={isUploadModalOpen} 
        onClose={() => setIsUploadModalOpen(false)} 
        onUploadSuccess={handleUploadSuccess} 
      />

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Visão Geral</h1>
          <p className="text-slate-500 mt-1">Acompanhe o processamento de lotes e o desempenho da turma.</p>
        </div>
        <button 
          onClick={() => setIsUploadModalOpen(true)}
          className="btn-primary flex items-center space-x-2 shadow-emerald-500/20 shadow-lg"
        >
          <UploadCloud className="w-5 h-5" />
          <span>Novo Lote PDF</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="glass-panel p-6 rounded-xl flex flex-col space-y-4 border-l-4 border-l-blue-500">
          <div className="flex justify-between items-start">
            <span className="text-sm font-medium text-slate-500 uppercase tracking-wider">Processando</span>
            <div className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <Clock className="w-5 h-5 text-blue-500" />
            </div>
          </div>
          <div>
            <h2 className="text-3xl font-bold text-slate-800 dark:text-slate-100">124</h2>
            <p className="text-sm text-slate-500 mt-1">Provas no pipeline OCR</p>
          </div>
        </div>

        <div className="glass-panel p-6 rounded-xl flex flex-col space-y-4 border-l-4 border-l-yellow-500">
          <div className="flex justify-between items-start">
            <span className="text-sm font-medium text-slate-500 uppercase tracking-wider">Revisão Pendente</span>
            <div className="p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
              <FileText className="w-5 h-5 text-yellow-600" />
            </div>
          </div>
          <div>
            <h2 className="text-3xl font-bold text-slate-800 dark:text-slate-100">42</h2>
            <p className="text-sm text-slate-500 mt-1">Aguardando seu aceite</p>
          </div>
        </div>

        <div className="glass-panel p-6 rounded-xl flex flex-col space-y-4 border-l-4 border-l-emerald-500">
          <div className="flex justify-between items-start">
            <span className="text-sm font-medium text-slate-500 uppercase tracking-wider">Provas Fechadas</span>
            <div className="p-2 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg">
              <CheckCircle className="w-5 h-5 text-emerald-500" />
            </div>
          </div>
          <div>
            <h2 className="text-3xl font-bold text-slate-800 dark:text-slate-100">890</h2>
            <p className="text-sm text-slate-500 mt-1">Corrigidas neste semestre</p>
          </div>
        </div>

        <div className="glass-panel p-6 rounded-xl flex flex-col space-y-4 border-l-4 border-l-purple-500">
          <div className="flex justify-between items-start">
            <span className="text-sm font-medium text-slate-500 uppercase tracking-wider">Média Geral</span>
            <div className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
              <BarChart3 className="w-5 h-5 text-purple-500" />
            </div>
          </div>
          <div>
            <h2 className="text-3xl font-bold text-slate-800 dark:text-slate-100">7.8</h2>
            <p className="text-sm text-slate-500 mt-1">+0.5 vs turma passada</p>
          </div>
        </div>
      </div>

      {/* Lotes Recentes */}
      <div className="glass-panel rounded-xl overflow-hidden mt-8 shadow-sm">
        <div className="p-6 border-b border-surface-border flex justify-between items-center">
          <h3 className="text-lg font-bold">Lotes Recentes (Uploads)</h3>
          <button className="text-sm text-emerald-600 font-medium hover:underline">Ver Todos</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/30 text-slate-500 text-xs uppercase tracking-wider font-semibold">
                <th className="px-6 py-4">Nome do Lote / Prova</th>
                <th className="px-6 py-4">Data</th>
                <th className="px-6 py-4">Progresso</th>
                <th className="px-6 py-4">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              <tr className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-colors">
                <td className="px-6 py-4">
                  <div className="font-medium text-slate-800 dark:text-slate-200">Turma A - Anatomia I</div>
                  <div className="text-xs text-slate-500 mt-0.5">batch_5f8a9e...</div>
                </td>
                <td className="px-6 py-4 text-sm text-slate-600">Hoje, 10:45</td>
                <td className="px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 w-full"></div>
                    </div>
                    <span className="text-sm font-medium text-emerald-600">Revisar (42)</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <Link href="/review">
                    <button className="text-sm text-emerald-700 dark:text-emerald-400 font-medium hover:text-emerald-800 bg-emerald-50 dark:bg-emerald-500/10 px-3 py-1.5 rounded-lg transition-colors">
                      Iniciar Revisão
                    </button>
                  </Link>
                </td>
              </tr>
              <tr className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-colors">
                <td className="px-6 py-4">
                  <div className="font-medium text-slate-800 dark:text-slate-200">Turma B - Bioquímica</div>
                  <div className="text-xs text-slate-500 mt-0.5">batch_2b1c3d...</div>
                </td>
                <td className="px-6 py-4 text-sm text-slate-600">Hoje, 11:30</td>
                <td className="px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 w-[65%] animate-pulse"></div>
                    </div>
                    <span className="text-sm font-medium text-blue-600">OCR...</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className="text-sm text-slate-400 cursor-not-allowed">Aguardando</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
