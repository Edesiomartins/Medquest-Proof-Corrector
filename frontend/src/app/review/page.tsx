import { CheckCircle, AlertCircle, MessageSquare } from 'lucide-react';
import Link from 'next/link';

export default function ReviewPage() {
  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col animate-in fade-in duration-500">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Revisão Assistida</h1>
          <p className="text-slate-500 text-sm mt-1">Lote: Turma A - Anatomia I • Resposta 1 de 42</p>
        </div>
        <div className="flex space-x-3">
          <Link href="/">
            <button className="btn-secondary">Ignorar p/ Fim</button>
          </Link>
          <button className="btn-primary flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-700 shadow-emerald-500/20 shadow-md">
            <CheckCircle className="w-4 h-4" />
            <span>Aprovar Nota (Enter)</span>
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-6 min-h-0">
        {/* Painel Esquerdo: Imagem da Prova */}
        <div className="flex-1 glass-panel rounded-xl flex flex-col overflow-hidden border border-surface-border shadow-sm">
          <div className="p-4 border-b border-surface-border bg-slate-50/80 dark:bg-slate-800/50 flex justify-between items-center">
            <h3 className="font-semibold text-slate-700 dark:text-slate-300">Recorte da Resposta</h3>
            <span className="px-2 py-1 bg-slate-200 dark:bg-slate-700 text-xs font-medium rounded text-slate-600 dark:text-slate-400">Pág 2 • Questão 3</span>
          </div>
          <div className="flex-1 bg-slate-200/50 dark:bg-slate-900/50 p-6 flex items-center justify-center relative overflow-auto">
            {/* Imagem simulada via CSS */}
            <div className="w-full max-w-lg bg-amber-50/50 dark:bg-slate-800 p-8 shadow-sm rotate-1 rounded-sm border border-amber-100/50 dark:border-slate-700">
              <p className="font-[cursive] text-slate-700 dark:text-slate-300 text-2xl leading-relaxed opacity-80 italic tracking-wide">
                A mitocôndria é a organela responsável pela respiração celular... 
                ela produz ATP que fornece energia pro corpo. Mas não sei qual a enzima.
              </p>
            </div>
          </div>
        </div>

        {/* Painel Direito: Análise da IA */}
        <div className="flex-[0.8] flex flex-col gap-4 overflow-y-auto min-h-0 pr-1">
          
          <div className="glass-panel p-6 rounded-xl border border-emerald-500/20 relative overflow-hidden shadow-sm">
            <div className="absolute top-0 left-0 w-1 h-full bg-emerald-500"></div>
            <div className="flex justify-between items-start mb-4">
              <h3 className="font-bold text-lg">Nota Sugerida pela IA</h3>
              <div className="flex items-baseline space-x-1">
                <span className="text-4xl font-black text-emerald-600 dark:text-emerald-400">1.5</span>
                <span className="text-slate-400 font-medium">/ 2.0</span>
              </div>
            </div>
            
            <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed bg-emerald-50/50 dark:bg-emerald-900/10 p-4 rounded-lg">
              <MessageSquare className="w-4 h-4 inline-block mr-2 text-emerald-600 mb-1" />
              O aluno identificou corretamente a função principal da mitocôndria (respiração e produção de ATP), mas perdeu pontuação por não citar a enzima ATP sintase conforme exigido no critério obrigatório.
            </p>
          </div>

          <div className="glass-panel p-6 rounded-xl border border-surface-border shadow-sm">
            <h3 className="font-bold mb-4 text-slate-700 dark:text-slate-300">Critérios de Correção</h3>
            <div className="space-y-4">
              <div className="flex items-start space-x-3">
                <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-200">Mencionar Produção de ATP (+1.0)</p>
                  <p className="text-xs text-slate-500 mt-0.5">Trecho extraído: "...ela produz ATP..."</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-200">Explicar Respiração Celular (+0.5)</p>
                </div>
              </div>
              <div className="flex items-start space-x-3 opacity-60">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium line-through">Citar ATP Sintase (+0.5)</p>
                  <p className="text-xs text-red-500 font-medium mt-0.5">Não encontrado na resposta.</p>
                </div>
              </div>
            </div>
          </div>

          <div className="glass-panel p-6 rounded-xl border border-surface-border shadow-sm mt-auto">
            <h3 className="font-bold mb-4 text-slate-700 dark:text-slate-300">Ajuste Manual</h3>
            <div className="flex items-center space-x-4 mb-4">
              <input type="range" min="0" max="2" step="0.1" defaultValue="1.5" className="flex-1 accent-emerald-500" />
              <input type="number" step="0.1" defaultValue="1.5" className="w-20 px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-center font-bold text-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500" />
            </div>
            <textarea 
              placeholder="Adicionar um comentário/feedback para o aluno (Opcional)..." 
              className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all resize-none h-20"
            ></textarea>
          </div>

        </div>
      </div>
    </div>
  );
}
