"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Plus, Save, Trash2, ListChecks, Target, LayoutTemplate } from 'lucide-react';
import { api } from '@/lib/api';

interface Rubric {
  id: string;
  criteria: string;
  score_impact: number;
  is_mandatory: boolean;
}

interface Question {
  id: string;
  question_text: string;
  expected_answer: string;
  max_score: number;
  page_number: number;
  box_x: number;
  box_y: number;
  box_w: number;
  box_h: number;
  rubrics: Rubric[];
}

export default function NewExamPage() {
  const router = useRouter();
  const [examName, setExamName] = useState("");
  const [maxScore, setMaxScore] = useState(10);
  const [questions, setQuestions] = useState<Question[]>([
    {
      id: crypto.randomUUID(),
      question_text: "",
      expected_answer: "",
      max_score: 10,
      page_number: 1,
      box_x: 0,
      box_y: 0,
      box_w: 1,
      box_h: 0.3,
      rubrics: [],
    },
  ]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const patchQuestion = (qId: string, patch: Partial<Question>) => {
    setQuestions((prev) =>
      prev.map((q) => (q.id === qId ? { ...q, ...patch } : q))
    );
  };

  const addQuestion = () => {
    setQuestions([
      ...questions,
      {
        id: crypto.randomUUID(),
        question_text: "",
        expected_answer: "",
        max_score: 0,
        page_number: 1,
        box_x: 0,
        box_y: 0,
        box_w: 1,
        box_h: 0.3,
        rubrics: [],
      },
    ]);
  };

  const addRubric = (qId: string) => {
    setQuestions(
      questions.map((q) => {
        if (q.id !== qId) return q;
        return {
          ...q,
          rubrics: [
            ...q.rubrics,
            {
              id: crypto.randomUUID(),
              criteria: "",
              score_impact: 1,
              is_mandatory: false,
            },
          ],
        };
      })
    );
  };

  const patchRubric = (qId: string, rId: string, patch: Partial<Rubric>) => {
    setQuestions(
      questions.map((q) => {
        if (q.id !== qId) return q;
        return {
          ...q,
          rubrics: q.rubrics.map((r) =>
            r.id === rId ? { ...r, ...patch } : r
          ),
        };
      })
    );
  };

  const handleSave = async () => {
    setSaveError(null);
    const name = examName.trim();
    if (!name) {
      setSaveError('Informe o nome da prova.');
      return;
    }
    for (const q of questions) {
      if (!q.question_text.trim() || !q.expected_answer.trim()) {
        setSaveError('Preencha enunciado e resposta esperada em todas as questões.');
        return;
      }
    }

    setIsSaving(true);
    try {
      const { data: exam } = await api.post<{
        id: string;
        template_id: string;
      }>('/exams', {
        name,
        max_score: maxScore,
      });

      for (const q of questions) {
        await api.post(`/exams/${exam.id}/questions`, {
          question_text: q.question_text.trim(),
          expected_answer: q.expected_answer.trim(),
          max_score: q.max_score,
          page_number: q.page_number,
          box_x: q.box_x,
          box_y: q.box_y,
          box_w: q.box_w,
          box_h: q.box_h,
        });
      }

      router.push('/exams');
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: unknown } } };
      const d = ax.response?.data?.detail;
      setSaveError(
        typeof d === 'string'
          ? d
          : 'Erro ao salvar. Verifique a API e o banco de dados.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in duration-500 pb-20">

      <div className="flex justify-between items-center">
        <div className="flex items-center space-x-4">
          <Link href="/exams">
            <button
              type="button"
              className="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors text-slate-500"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Criar Novo Template</h1>
            <p className="text-slate-500 text-sm mt-0.5">Defina as questões e rubricas da prova.</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={isSaving}
          className="btn-primary flex items-center space-x-2"
        >
          <Save className="w-4 h-4" />
          <span>{isSaving ? 'Salvando...' : 'Salvar Template'}</span>
        </button>
      </div>

      {saveError ? (
        <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {saveError}
        </div>
      ) : null}

      <div className="glass-panel p-6 rounded-xl border border-surface-border shadow-sm space-y-4">
        <div className="flex items-center space-x-2 border-b border-surface-border pb-4 mb-4">
          <LayoutTemplate className="w-5 h-5 text-emerald-600" />
          <h2 className="text-lg font-bold">1. Configuração Geral</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Nome da Prova
            </label>
            <input
              type="text"
              value={examName}
              onChange={(e) => setExamName(e.target.value)}
              placeholder="Ex: Anatomia I - P1"
              className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Nota Máxima Total
            </label>
            <input
              type="number"
              value={maxScore}
              onChange={(e) => setMaxScore(Number(e.target.value))}
              className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <div className="flex items-center space-x-2 mb-2">
          <ListChecks className="w-5 h-5 text-emerald-600" />
          <h2 className="text-lg font-bold">2. Questões e Rubricas</h2>
        </div>

        {questions.map((q, qIndex) => (
          <div
            key={q.id}
            className="glass-panel p-6 rounded-xl border border-surface-border shadow-sm relative overflow-hidden"
          >
            <div className="absolute top-0 left-0 w-1 h-full bg-emerald-500" />

            <div className="flex justify-between items-start mb-6">
              <h3 className="font-bold text-lg">Questão {qIndex + 1}</h3>
              {questions.length > 1 && (
                <button
                  type="button"
                  onClick={() =>
                    setQuestions(questions.filter((quest) => quest.id !== q.id))
                  }
                  className="text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 p-2 rounded-lg transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="space-y-6">
              <div className="grid grid-cols-4 gap-4">
                <div className="col-span-3">
                  <label className="block text-xs font-medium text-slate-500 mb-1">Enunciado</label>
                  <textarea
                    value={q.question_text}
                    onChange={(e) =>
                      patchQuestion(q.id, { question_text: e.target.value })
                    }
                    placeholder="Descreva a pergunta feita ao aluno..."
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 text-sm resize-none h-20 outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
                <div className="col-span-1">
                  <label className="block text-xs font-medium text-slate-500 mb-1">
                    Valor (Pontos)
                  </label>
                  <input
                    type="number"
                    value={q.max_score}
                    onChange={(e) =>
                      patchQuestion(q.id, { max_score: Number(e.target.value) })
                    }
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">
                  Resposta Esperada (Gabarito)
                </label>
                <textarea
                  value={q.expected_answer}
                  onChange={(e) =>
                    patchQuestion(q.id, { expected_answer: e.target.value })
                  }
                  placeholder="Resposta modelo para a IA comparar..."
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 text-sm resize-none h-24 outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>

              <div className="bg-slate-50 dark:bg-slate-800/50 p-4 rounded-lg border border-slate-200 dark:border-slate-700">
                <div className="flex items-center space-x-2 mb-3">
                  <Target className="w-4 h-4 text-emerald-600" />
                  <span className="text-sm font-bold text-slate-700 dark:text-slate-300">
                    Coordenadas de Leitura (OCR)
                  </span>
                </div>
                <div className="grid grid-cols-5 gap-4">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Página</label>
                    <input
                      type="number"
                      value={q.page_number}
                      onChange={(e) =>
                        patchQuestion(q.id, {
                          page_number: Number(e.target.value),
                        })
                      }
                      className="w-full p-2 text-sm border rounded bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Início X (0–1)</label>
                    <input
                      type="number"
                      step={0.01}
                      value={q.box_x}
                      onChange={(e) =>
                        patchQuestion(q.id, { box_x: Number(e.target.value) })
                      }
                      className="w-full p-2 text-sm border rounded bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Início Y (0–1)</label>
                    <input
                      type="number"
                      step={0.01}
                      value={q.box_y}
                      onChange={(e) =>
                        patchQuestion(q.id, { box_y: Number(e.target.value) })
                      }
                      className="w-full p-2 text-sm border rounded bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Largura</label>
                    <input
                      type="number"
                      step={0.01}
                      value={q.box_w}
                      onChange={(e) =>
                        patchQuestion(q.id, { box_w: Number(e.target.value) })
                      }
                      className="w-full p-2 text-sm border rounded bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Altura</label>
                    <input
                      type="number"
                      step={0.01}
                      value={q.box_h}
                      onChange={(e) =>
                        patchQuestion(q.id, { box_h: Number(e.target.value) })
                      }
                      className="w-full p-2 text-sm border rounded bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700"
                    />
                  </div>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-3">
                  <label className="block text-sm font-bold text-slate-700 dark:text-slate-300">
                    Rubricas (opcional — persistência em breve)
                  </label>
                  <button
                    type="button"
                    onClick={() => addRubric(q.id)}
                    className="text-xs text-emerald-600 font-medium hover:underline flex items-center"
                  >
                    <Plus className="w-3 h-3 mr-1" /> Adicionar Critério
                  </button>
                </div>

                {q.rubrics.length === 0 ? (
                  <div className="text-center py-4 border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-lg text-slate-400 text-sm">
                    Nenhum critério adicionado. A correção usará só o gabarito acima.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {q.rubrics.map((r) => (
                      <div
                        key={r.id}
                        className="flex items-center space-x-3 bg-white dark:bg-slate-800 p-3 rounded-lg border border-slate-200 dark:border-slate-700"
                      >
                        <input
                          type="text"
                          value={r.criteria}
                          onChange={(e) =>
                            patchRubric(q.id, r.id, { criteria: e.target.value })
                          }
                          placeholder="Ex: Explicou o processo corretamente"
                          className="flex-1 bg-transparent text-sm outline-none"
                        />
                        <div className="w-px h-6 bg-slate-200 dark:bg-slate-700" />
                        <input
                          type="number"
                          value={r.score_impact}
                          onChange={(e) =>
                            patchRubric(q.id, r.id, {
                              score_impact: Number(e.target.value),
                            })
                          }
                          placeholder="Pts"
                          className="w-16 bg-transparent text-sm outline-none text-center"
                        />
                        <div className="w-px h-6 bg-slate-200 dark:bg-slate-700" />
                        <label className="flex items-center space-x-2 text-xs text-slate-500 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={r.is_mandatory}
                            onChange={(e) =>
                              patchRubric(q.id, r.id, {
                                is_mandatory: e.target.checked,
                              })
                            }
                            className="accent-emerald-500"
                          />
                          <span>Obrigatório</span>
                        </label>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        <button
          type="button"
          onClick={addQuestion}
          className="w-full py-4 border-2 border-dashed border-emerald-200 dark:border-emerald-800 rounded-xl text-emerald-600 dark:text-emerald-500 font-medium hover:bg-emerald-50 dark:hover:bg-emerald-900/10 transition-colors flex items-center justify-center space-x-2"
        >
          <Plus className="w-5 h-5" />
          <span>Adicionar Outra Questão</span>
        </button>
      </div>
    </div>
  );
}
