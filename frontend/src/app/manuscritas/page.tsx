"use client";

import { FormEvent, useMemo, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, FileUp, Loader2, ScanText } from 'lucide-react';
import { visualExamAnalysisApi } from '@/lib/api';

type Grade = {
  score: number | null;
  max_score: number | null;
  verdict: string;
  justification: string;
  needs_human_review: boolean;
  review_reason?: string;
};

type QuestionResult = {
  number: number;
  question_number?: number;
  extracted_answer?: string;
  answer_transcription: string;
  reading_confidence: string;
  ocr_confidence?: number | null;
  reading_notes: string;
  image_region?: unknown;
  grade: Grade;
};

type StudentResult = {
  student: { name?: string; registration?: string; class?: string; student_code?: string };
  page: number;
  physical_page?: number;
  detected_student_name?: string;
  detected_registration?: string;
  detected_student_code?: string;
  questions: QuestionResult[];
};

type VisualExamResponse = {
  status: string;
  pdf_name: string;
  pages_processed: number;
  students: StudentResult[];
  warnings: string[];
};

const visionModels = [
  'qwen/qwen2.5-vl-72b-instruct',
  'qwen/qwen2.5-vl-32b-instruct',
  'qwen/qwen-2.5-vl-7b-instruct',
  'google/gemini-2.5-flash',
];

const textModels = [
  'openai/gpt-oss-120b',
  'openai/gpt-oss-20b',
  'meta-llama/llama-3.1-8b-instruct',
  'qwen/qwen3-235b-a22b-2507',
];

export default function VisualExamPage() {
  const [file, setFile] = useState<File | null>(null);
  const [rubric, setRubric] = useState('');
  const [visionModel, setVisionModel] = useState(visionModels[0]);
  const [textModel, setTextModel] = useState(textModels[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<VisualExamResponse | null>(null);
  const [selectedStudentKey, setSelectedStudentKey] = useState('');

  const studentGroups = useMemo(() => {
    const groups = new Map<string, { label: string; students: StudentResult[] }>();
    for (const item of result?.students || []) {
      const code = (item.detected_student_code || item.student.student_code || '').trim();
      const registration = (item.detected_registration || item.student.registration || '').trim();
      const key = code || registration || `page-${item.physical_page || item.page}`;
      const labelBase = code ? `Aluno ${code}` : (item.detected_student_name || item.student.name || 'Aluno não identificado');
      const label = registration ? `${labelBase} (${registration})` : labelBase;
      if (!groups.has(key)) groups.set(key, { label, students: [] });
      groups.get(key)?.students.push(item);
    }
    return Array.from(groups.entries()).map(([key, value]) => ({ key, ...value }));
  }, [result]);

  const effectiveStudentKey = selectedStudentKey || studentGroups[0]?.key || '';

  const rows = useMemo(() => {
    const group = studentGroups.find((item) => item.key === effectiveStudentKey);
    return (group?.students || []).flatMap((student) => student.questions.map((question) => ({ student, question })));
  }, [studentGroups, effectiveStudentKey]);

  const hasStudentMismatchWarning = useMemo(() => {
    if (!effectiveStudentKey) return false;
    return rows.some(({ student }) => {
      const detectedCode = (student.detected_student_code || student.student.student_code || '').trim();
      const detectedRegistration = (student.detected_registration || student.student.registration || '').trim();
      return detectedCode !== effectiveStudentKey && detectedRegistration !== effectiveStudentKey;
    });
  }, [rows, effectiveStudentKey]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) {
      setError('Selecione um PDF.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const body = new FormData();
      body.append('file', file);
      if (rubric.trim()) body.append('rubric', rubric.trim());
      if (visionModel) body.append('vision_model', visionModel);
      if (textModel) body.append('text_model', textModel);

      const { data } = await visualExamAnalysisApi.post<VisualExamResponse>('/analyze-discursive-pdf', body);
      setResult(data);
      setSelectedStudentKey('');
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Falha ao analisar o PDF.');
      } else {
        setError('Falha ao analisar o PDF.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Correção Visual de Provas Discursivas</h1>
          <p className="text-slate-500 mt-1">Leitura visual multimodal e correção por rubrica.</p>
        </div>
        <ScanText className="w-9 h-9 text-emerald-600" />
      </div>

      <form onSubmit={submit} className="glass-panel rounded-xl p-6 space-y-5">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <label className="space-y-2">
            <span className="text-sm font-medium">PDF escaneado</span>
            <input
              type="file"
              accept="application/pdf"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
              className="block w-full text-sm file:mr-4 file:rounded-lg file:border-0 file:bg-emerald-50 file:px-4 file:py-2 file:font-medium file:text-emerald-700 hover:file:bg-emerald-100"
            />
          </label>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="space-y-2">
              <span className="text-sm font-medium">Modelo de visão</span>
              <select value={visionModel} onChange={(event) => setVisionModel(event.target.value)} className="w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm">
                {visionModels.map((model) => <option key={model} value={model}>{model}</option>)}
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium">Modelo textual</span>
              <select value={textModel} onChange={(event) => setTextModel(event.target.value)} className="w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm">
                {textModels.map((model) => <option key={model} value={model}>{model}</option>)}
              </select>
            </label>
          </div>
        </div>

        <label className="space-y-2 block">
          <span className="text-sm font-medium">Gabarito / rubrica em JSON</span>
          <textarea
            value={rubric}
            onChange={(event) => setRubric(event.target.value)}
            rows={8}
            className="w-full rounded-lg border border-surface-border bg-surface px-3 py-2 font-mono text-sm"
            placeholder='{"questions":[{"number":1,"prompt":"...","max_score":1,"expected_answer":"...","essential_concepts":["..."]}]}'
          />
        </label>

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertTriangle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        <button type="submit" disabled={loading} className="btn-primary inline-flex items-center gap-2 disabled:opacity-60">
          {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileUp className="w-5 h-5" />}
          <span>Analisar prova discursiva</span>
        </button>
      </form>

      {result && (
        <div className="glass-panel rounded-xl overflow-hidden">
          <div className="p-5 border-b border-surface-border flex justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold">{result.pdf_name}</h2>
              <p className="text-sm text-slate-500">{result.pages_processed} página(s) processada(s)</p>
            </div>
            {result.warnings.length > 0 && (
              <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                {result.warnings[0]}
              </div>
            )}
          </div>
          <div className="px-5 py-4 border-b border-surface-border flex items-center gap-4">
            <label className="text-sm font-medium">Aluno detectado</label>
            <select
              value={effectiveStudentKey}
              onChange={(event) => setSelectedStudentKey(event.target.value)}
              className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm min-w-72"
            >
              {studentGroups.map((group) => (
                <option key={group.key} value={group.key}>
                  {group.label}
                </option>
              ))}
            </select>
          </div>
          {hasStudentMismatchWarning && (
            <div className="mx-5 mt-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              <AlertTriangle className="w-4 h-4" />
              <span>Possível divergência de vinculação aluno-página</span>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50/70 dark:bg-slate-800/40 text-slate-500 uppercase text-xs">
                  <th className="px-4 py-3">Aluno</th>
                  <th className="px-4 py-3">Matrícula</th>
                  <th className="px-4 py-3">Turma</th>
                  <th className="px-4 py-3">Página física</th>
                  <th className="px-4 py-3">Questão</th>
                  <th className="px-4 py-3 min-w-80">Transcrição</th>
                  <th className="px-4 py-3">Confiança</th>
                  <th className="px-4 py-3">OCR conf.</th>
                  <th className="px-4 py-3">Nota</th>
                  <th className="px-4 py-3">Veredito</th>
                  <th className="px-4 py-3 min-w-72">Justificativa</th>
                  <th className="px-4 py-3">Revisão</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {rows.map(({ student, question }) => {
                  const lowReading = question.reading_confidence === 'baixa';
                  const zeroScore = question.grade?.score === 0;
                  const review = question.grade?.needs_human_review || lowReading;
                  return (
                    <tr key={`${student.physical_page || student.page}-${question.question_number || question.number}`} className={review ? 'bg-amber-50/60 dark:bg-amber-500/10' : ''}>
                      <td className="px-4 py-3 font-medium">{student.detected_student_name || student.student.name || 'Não identificado'}</td>
                      <td className="px-4 py-3">{student.detected_registration || student.student.registration || '-'}</td>
                      <td className="px-4 py-3">{student.student.class || '-'}</td>
                      <td className="px-4 py-3">{student.physical_page || student.page}</td>
                      <td className="px-4 py-3">{question.question_number || question.number}</td>
                      <td className="px-4 py-3 whitespace-pre-wrap">{question.extracted_answer || question.answer_transcription || '[sem resposta]'}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded px-2 py-1 text-xs font-medium ${lowReading ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
                          {question.reading_confidence}
                        </span>
                      </td>
                      <td className="px-4 py-3">{question.ocr_confidence != null ? `${Math.round(question.ocr_confidence * 100)}%` : '-'}</td>
                      <td className={`px-4 py-3 font-semibold ${zeroScore ? 'text-red-700' : ''}`}>
                        {question.grade?.score ?? '-'} / {question.grade?.max_score ?? '-'}
                      </td>
                      <td className="px-4 py-3">{question.grade?.verdict || '-'}</td>
                      <td className="px-4 py-3">{question.grade?.justification || question.reading_notes || '-'}</td>
                      <td className="px-4 py-3">
                        <div className="mb-2 text-xs font-medium">{review ? 'sim' : 'não'}</div>
                        <button className={`rounded-lg px-3 py-1.5 text-xs font-medium ${review ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600'}`}>
                          revisar manualmente
                        </button>
                        <div className="mt-2 flex flex-col gap-1">
                          <button className="text-xs text-slate-600 underline">editar transcrição</button>
                          <button className="text-xs text-slate-600 underline">editar nota sugerida</button>
                          <button className="text-xs text-emerald-700 underline">salvar correção final</button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
