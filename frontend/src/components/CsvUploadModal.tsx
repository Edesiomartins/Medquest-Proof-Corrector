"use client";
import { useState } from 'react';
import { X, Upload, File as FileIcon, CheckCircle2, AlertCircle, Loader2, TableProperties } from 'lucide-react';
import { uploadApi } from '@/lib/api';

interface CsvUploadModalProps {
  isOpen: boolean;
  classId: string;
  onClose: () => void;
  onUploadSuccess: () => void;
}

export default function CsvUploadModal({ isOpen, classId, onClose, onUploadSuccess }: CsvUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (!selectedFile.name.endsWith('.csv')) {
        setError('Por favor, selecione apenas arquivos .csv');
        return;
      }
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Por favor, selecione um arquivo CSV.');
      return;
    }
    
    setIsUploading(true);
    setError(null);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      // Chamada para a rota de importação de CSV do FastAPI
      await uploadApi.post(`/classes/${classId}/students/csv`, formData);
      onUploadSuccess();
      onClose();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') setError(detail);
      else setError('Erro de conexão ou formato do CSV inválido. Certifique-se de que existem as colunas "nome" e "matricula" (curso e turma são opcionais).');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden border border-slate-200 dark:border-slate-800">
        
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center space-x-2">
            <TableProperties className="w-5 h-5 text-emerald-600" />
            <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100">Importar Alunos (CSV)</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Body */}
        <div className="p-6 space-y-6">
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Você pode enviar a <strong>planilha original exportada pelo sistema da Universidade</strong>.
            Nossa Inteligência Artificial localizará dinamicamente as colunas de <i>Matrícula</i> e <i>Nome do Aluno</i>,
            e também importa <i>Curso</i> e <i>Turma</i> quando estiverem presentes.
          </p>

          {/* Upload Area */}
          <div className="border-2 border-dashed border-emerald-500/30 rounded-xl bg-emerald-50/50 dark:bg-emerald-900/10 p-8 flex flex-col items-center justify-center text-center transition-colors hover:bg-emerald-50 dark:hover:bg-emerald-900/20">
            {!file ? (
              <>
                <div className="w-12 h-12 bg-white dark:bg-slate-800 rounded-full flex items-center justify-center shadow-sm text-emerald-500 mb-4">
                  <Upload className="w-6 h-6" />
                </div>
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Arraste a Planilha CSV aqui
                </p>
                <p className="text-xs text-slate-500 mb-4">Ou clique para buscar no computador</p>
                
                <label className="btn-secondary text-sm cursor-pointer border-emerald-200 dark:border-emerald-800 hover:border-emerald-300">
                  <span>Selecionar Arquivo .CSV</span>
                  <input type="file" accept=".csv" className="hidden" onChange={handleFileChange} />
                </label>
              </>
            ) : (
              <div className="flex items-center space-x-3 bg-white dark:bg-slate-800 p-4 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 w-full">
                <FileIcon className="w-8 h-8 text-emerald-500" />
                <div className="flex-1 text-left overflow-hidden">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">{file.name}</p>
                  <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(2)} KB</p>
                </div>
                <button onClick={() => setFile(null)} className="text-slate-400 hover:text-red-500 p-1">
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-center space-x-2 text-sm text-red-600 bg-red-50 dark:bg-red-900/20 p-3 rounded-lg border border-red-100 dark:border-red-800/30">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="flex justify-end space-x-3 p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/30">
          <button onClick={onClose} disabled={isUploading} className="btn-secondary px-6">
            Cancelar
          </button>
          <button 
            onClick={handleUpload} 
            disabled={!file || isUploading}
            className={`btn-primary px-6 flex items-center space-x-2 ${(!file || isUploading) ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isUploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Importando...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>Confirmar Importação</span>
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
}
