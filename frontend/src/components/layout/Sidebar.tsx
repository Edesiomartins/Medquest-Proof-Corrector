import Link from 'next/link';
import { Home, FileText, CheckSquare, Users, ScanText } from 'lucide-react';

export default function Sidebar() {
  return (
    <aside className="w-64 h-screen glass-panel flex flex-col fixed left-0 top-0 border-r border-surface-border">
      <div className="px-4 py-5 border-b border-surface-border/60 flex items-center justify-center">
        <img
          src="/medquest-logo.png"
          alt="MedQuest Correção"
          className="w-48 h-auto object-contain"
        />
      </div>

      <nav className="flex-1 px-4 space-y-1 mt-4">
        <Link href="/" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 font-medium">
          <Home className="w-5 h-5" />
          <span>Dashboard</span>
        </Link>
        <Link href="/classes" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
          <Users className="w-5 h-5" />
          <span>Turmas & Alunos</span>
        </Link>
        <Link href="/exams" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
          <FileText className="w-5 h-5" />
          <span>Provas & Templates</span>
        </Link>
        <Link href="/review" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
          <CheckSquare className="w-5 h-5" />
          <span>Revisão Pendente</span>
        </Link>
        <Link href="/manuscritas" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
          <ScanText className="w-5 h-5" />
          <span>Prova manuscrita</span>
        </Link>
      </nav>
    </aside>
  );
}
