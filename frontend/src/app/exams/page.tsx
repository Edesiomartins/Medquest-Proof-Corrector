"use client";

import { type ChangeEvent, useEffect, useRef, useState } from 'react';
import {
  Plus,
  BookOpen,
  FileDown,
  Loader2,
  Pencil,
  Trash2,
  Upload,
  X,
  CheckCircle2,
  RotateCcw,
} from 'lucide-react';
import Link from 'next/link';
import { api, uploadApi } from '@/lib/api';

type ExamSummary = {
  id: string;
  name: string;
  class_id: string | null;
  question_count: number;
};

type UploadBatchResponse = {
  batch_id: string;
  status: string;
};

type UploadBatchStatusResponse = {
  batch_id: string;
  status: string;
  total_pages: number;
};

const TERMINAL_BATCH_STATUSES = new Set(['REVIEW_PENDING', 'DONE', 'FAILED']);

function getBatchStatusLabel(status: string | null): string {
  if (!status) return 'Aguardando envio';
  if (status === 'PENDING') return 'Na fila';
  if (status === 'PROCESSING') return 'Processando';
  if (status === 'REVIEW_PENDING') return 'Pronto para revisão';
  if (status === 'DONE') return 'Concluído';
  if (status === 'FAILED') return 'Falhou';
  return status;
}

function getBatchStatusClass(status: string | null): string {
  if (status === 'FAILED') {
    return 'border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300';
  }
  if (status === 'REVIEW_PENDING' || status === 'DONE') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-300';
  }
  return 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-300';
}

export default function ExamsPage() {
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [pendingLogoExam, setPendingLogoExam] = useState<{ id: string; name: string } | null>(null);
  const logoInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadModalExam, setUploadModalExam] = useState<ExamSummary | null>(null);
  const [correctionFile, setCorrectionFile] = useState<File | null>(null);
  const [uploadingCorrection, setUploadingCorrection] = useState(false);
  const [forcingProcessing, setForcingProcessing] = useState(false);
  const [correctionError, setCorrectionError] = useState<string | null>(null);
  const [uploadedBatchId, setUploadedBatchId] = useState<string | null>(null);
  const [uploadedBatchStatus, setUploadedBatchStatus] = useState<string | null>(null);
  const [uploadedBatchPages, setUploadedBatchPages] = useState<number>(0);
  const [batchRefreshKey, setBatchRefreshKey] = useState(0);
  const [reprocessing, setReprocessing] = useState(false);
  const canStartReview = uploadedBatchStatus === 'REVIEW_PENDING';
  const canReprocess =
    Boolean(uploadedBatchId) &&
    uploadedBatchStatus != null &&
    uploadedBatchStatus !== 'PROCESSING';

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

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadExams();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleDownloadSheets = async (examId: string, examName: string, logoFile: File) => {
    setDownloadingId(examId);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('logo', logoFile);
      const response = await uploadApi.post(`/exams/${examId}/answer-sheets`, formData, { responseType: 'blob' });
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

  const handleRequestLogoAndDownload = (examId: string, examName: string) => {
    setPendingLogoExam({ id: examId, name: examName });
    logoInputRef.current?.click();
  };

  const handleLogoSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const selectedLogo = event.target.files?.[0];
    const exam = pendingLogoExam;
    event.target.value = '';
    setPendingLogoExam(null);

    if (!exam || !selectedLogo) return;
    await handleDownloadSheets(exam.id, exam.name, selectedLogo);
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

  const triggerBatchPollRefresh = () => setBatchRefreshKey((k) => k + 1);

  const handleReprocessBatch = async () => {
    if (!uploadedBatchId) return;
    setReprocessing(true);
    setCorrectionError(null);
    try {
      const { data } = await api.post<UploadBatchResponse>(`/batches/${uploadedBatchId}/reprocess`);
      setUploadedBatchStatus(data.status);
      setUploadedBatchPages(0);
      triggerBatchPollRefresh();
    } catch (err: unknown) {
      let msg = 'Não foi possível reprocessar o lote.';
      if (err && typeof err === 'object' && 'response' in err) {
        const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
        if (detail) msg = detail;
      }
      setCorrectionError(msg);
    } finally {
      setReprocessing(false);
    }
  };

  const handleReuploadBatch = async () => {
    if (!uploadModalExam || !uploadedBatchId || !correctionFile) return;
    setUploadingCorrection(true);
    setCorrectionError(null);
    try {
      const formData = new FormData();
      formData.append('file', correctionFile);
      formData.append('exam_id', uploadModalExam.id);
      const { data } = await uploadApi.post<UploadBatchResponse>(
        `/batches/${uploadedBatchId}/reupload`,
        formData,
      );
      setUploadedBatchStatus(data.status);
      setUploadedBatchPages(0);
      triggerBatchPollRefresh();
    } catch (err: unknown) {
      let msg = 'Não foi possível substituir o PDF e reprocessar.';
      if (err && typeof err === 'object' && 'response' in err) {
        const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
        if (detail) msg = detail;
      }
      setCorrectionError(msg);
    } finally {
      setUploadingCorrection(false);
    }
  };

  const openCorrectionModal = (exam: ExamSummary) => {
    setUploadModalExam(exam);
    setCorrectionFile(null);
    setUploadedBatchId(null);
    setUploadedBatchStatus(null);
    setUploadedBatchPages(0);
    setBatchRefreshKey(0);
    setForcingProcessing(false);
    setCorrectionError(null);
  };

  const closeCorrectionModal = () => {
    if (uploadingCorrection) return;
    setUploadModalExam(null);
    setCorrectionFile(null);
    setUploadedBatchId(null);
    setUploadedBatchStatus(null);
    setUploadedBatchPages(0);
    setBatchRefreshKey(0);
    setForcingProcessing(false);
    setCorrectionError(null);
  };

  const handleUploadForCorrection = async () => {
    if (!uploadModalExam) return;
    if (!correctionFile) {
      setCorrectionError('Selecione o PDF preenchido dos alunos.');
      return;
    }

    setUploadingCorrection(true);
    setCorrectionError(null);
    try {
      const formData = new FormData();
      formData.append('file', correctionFile);
      formData.append('exam_id', uploadModalExam.id);

      const { data } = await uploadApi.post<UploadBatchResponse>('/batches/upload', formData);
      setUploadedBatchId(data.batch_id);
      setUploadedBatchStatus(data.status);
      setUploadedBatchPages(0);
    } catch (err: unknown) {
      let msg = 'Falha ao enviar o lote para correção.';
      if (err && typeof err === 'object' && 'response' in err) {
        const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
        if (detail) msg = detail;
      }
      setCorrectionError(msg);
    } finally {
      setUploadingCorrection(false);
    }
  };

  const handleProcessBatchNow = async () => {
    if (!uploadedBatchId) return;
    setForcingProcessing(true);
    setCorrectionError(null);
    try {
      const { data } = await api.post<UploadBatchStatusResponse>(`/batches/${uploadedBatchId}/process-now`);
      setUploadedBatchStatus(data.status);
      setUploadedBatchPages(data.total_pages);
    } catch (err: unknown) {
      let msg = 'Não foi possível iniciar o processamento manual do lote.';
      if (err && typeof err === 'object' && 'response' in err) {
        const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
        if (detail) msg = detail;
      }
      setCorrectionError(msg);
    } finally {
      setForcingProcessing(false);
    }
  };

  useEffect(() => {
    if (!uploadModalExam || !uploadedBatchId) return;

    let cancelled = false;
    let timerId: number | undefined;

    const fetchBatchStatus = async () => {
      try {
        const { data } = await api.get<UploadBatchStatusResponse>(`/batches/${uploadedBatchId}/status`);
        if (cancelled) return;

        setUploadedBatchStatus(data.status);
        setUploadedBatchPages(data.total_pages);

        if (!TERMINAL_BATCH_STATUSES.has(data.status)) {
          timerId = window.setTimeout(() => {
            void fetchBatchStatus();
          }, 2500);
        }
      } catch {
        if (cancelled) return;
        setUploadedBatchStatus('FAILED');
        setCorrectionError('Não foi possível consultar o status do lote.');
      }
    };

    timerId = window.setTimeout(() => {
      void fetchBatchStatus();
    }, 0);

    return () => {
      cancelled = true;
      if (timerId) window.clearTimeout(timerId);
    };
  }, [uploadModalExam, uploadedBatchId, batchRefreshKey]);

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <input
        ref={logoInputRef}
        type="file"
        accept="image/png,image/jpeg,image/jpg,image/webp"
        className="hidden"
        onChange={handleLogoSelected}
      />

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
                          onClick={() => handleRequestLogoAndDownload(ex.id, ex.name)}
                          disabled={!ex.class_id || ex.question_count === 0 || downloadingId === ex.id}
                          className="p-2 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-400 transition-colors rounded-lg inline-flex items-center space-x-1.5 text-xs font-medium border border-emerald-200 dark:border-emerald-800 disabled:opacity-40 disabled:cursor-not-allowed"
                          title={!ex.class_id ? "Vincule a prova a uma turma primeiro" : ex.question_count === 0 ? "Adicione questões primeiro" : "Selecionar logo da IESE e baixar folhas-resposta"}
                        >
                          {downloadingId === ex.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />}
                          <span>Folhas</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => openCorrectionModal(ex)}
                          disabled={!ex.class_id || ex.question_count === 0}
                          className="p-2 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400 transition-colors rounded-lg inline-flex items-center space-x-1.5 text-xs font-medium border border-blue-200 dark:border-blue-800 disabled:opacity-40 disabled:cursor-not-allowed"
                          title={!ex.class_id ? "Vincule a prova a uma turma primeiro" : ex.question_count === 0 ? "Adicione questões primeiro" : "Enviar folhas preenchidas para correção"}
                        >
                          <Upload className="w-3.5 h-3.5" />
                          <span>Corrigir</span>
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

      {uploadModalExam && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 dark:border-slate-800">
              <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">
                Upload para correção
              </h2>
              <button type="button" onClick={closeCorrectionModal} disabled={uploadingCorrection} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 px-6 py-5">
              <p className="text-sm text-slate-600 dark:text-slate-300">
                Prova selecionada: <span className="font-semibold">{uploadModalExam.name}</span>
              </p>

              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-emerald-300 bg-emerald-50 px-4 py-4 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-900/10 dark:text-emerald-300 dark:hover:bg-emerald-900/20">
                <Upload className="h-4 w-4" />
                <span>{correctionFile ? 'Trocar PDF preenchido' : 'Selecionar PDF preenchido'}</span>
                <input
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(event) => {
                    const next = event.target.files?.[0] ?? null;
                    setCorrectionFile(next);
                    setCorrectionError(null);
                    if (!uploadedBatchId) {
                      setUploadedBatchStatus(null);
                      setUploadedBatchPages(0);
                      setForcingProcessing(false);
                    }
                  }}
                />
              </label>

              {correctionFile && (
                <p className="text-xs text-slate-500">
                  Arquivo: <span className="font-medium">{correctionFile.name}</span>
                </p>
              )}

              {correctionError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                  {correctionError}
                </div>
              )}

              {uploadedBatchId && (
                <div className={`rounded-lg border px-3 py-2 text-sm ${getBatchStatusClass(uploadedBatchStatus)}`}>
                  <div className="flex items-center gap-2">
                    {uploadedBatchStatus === 'PROCESSING' ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4" />
                    )}
                    <span>
                      Lote enviado. Status: <span className="font-semibold">{getBatchStatusLabel(uploadedBatchStatus)}</span>
                    </span>
                  </div>
                  <p className="mt-1 text-xs opacity-90">Páginas detectadas: {uploadedBatchPages}</p>
                  {!canStartReview && (
                    <p className="mt-1 text-xs opacity-90">
                      Aguarde o status &quot;Pronto para revisão&quot; para liberar o botão Corrigir agora.
                    </p>
                  )}
                  {uploadedBatchStatus === 'PENDING' && (
                    <button
                      type="button"
                      onClick={handleProcessBatchNow}
                      disabled={forcingProcessing}
                      className="mt-2 inline-flex items-center gap-2 rounded-md border border-blue-300 px-2.5 py-1 text-xs font-medium hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-blue-700 dark:hover:bg-blue-900/30"
                    >
                      {forcingProcessing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                      <span>Processar agora</span>
                    </button>
                  )}
                  {canReprocess && (
                    <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-200/80 pt-3 dark:border-slate-600/50">
                      <button
                        type="button"
                        onClick={() => void handleReprocessBatch()}
                        disabled={reprocessing || uploadingCorrection}
                        className="inline-flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100 dark:hover:bg-amber-900/40"
                        title="Apaga notas deste lote e processa de novo o mesmo PDF no servidor (nova vinculação por QR)."
                      >
                        {reprocessing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
                        Reprocessar lote (mesmo PDF)
                      </button>
                      {correctionFile ? (
                        <button
                          type="button"
                          onClick={() => void handleReuploadBatch()}
                          disabled={uploadingCorrection || reprocessing}
                          className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:hover:bg-slate-800"
                          title="Substitui o arquivo do lote pelo PDF selecionado acima e reprocessa."
                        >
                          {uploadingCorrection ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                          Substituir PDF e reprocessar
                        </button>
                      ) : null}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-slate-200 bg-slate-50 px-6 py-4 dark:border-slate-800 dark:bg-slate-800/30">
              <button
                type="button"
                onClick={closeCorrectionModal}
                disabled={uploadingCorrection}
                className="btn-secondary px-4"
              >
                Fechar
              </button>

              <button
                type="button"
                onClick={handleUploadForCorrection}
                disabled={uploadingCorrection || !correctionFile}
                className="btn-primary inline-flex items-center gap-2 px-4 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {uploadingCorrection ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                <span>Enviar para correção</span>
              </button>

              <Link href="/review">
                <button
                  type="button"
                  disabled={!canStartReview}
                  className="btn-primary px-4 disabled:cursor-not-allowed disabled:opacity-50"
                  title={canStartReview ? 'Abrir tela de revisão' : 'Disponível quando o lote estiver pronto para revisão'}
                >
                  Corrigir agora
                </button>
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
