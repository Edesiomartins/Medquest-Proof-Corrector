import Link from 'next/link';
import { Home, FileText, CheckSquare, Users } from 'lucide-react';

export default function Sidebar() {
  return (
    <aside className="w-64 h-screen glass-panel flex flex-col fixed left-0 top-0 border-r border-surface-border">
      <div className="p-6 flex items-center space-x-3">
        <div className="w-8 h-8 rounded bg-emerald-500 flex items-center justify-center text-white font-bold text-xl shadow-md shadow-emerald-500/20">
          M
        </div>
        <span className="font-bold text-xl tracking-tight text-foreground">Medquest</span>
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
      </nav>
    </aside>
  );
}
