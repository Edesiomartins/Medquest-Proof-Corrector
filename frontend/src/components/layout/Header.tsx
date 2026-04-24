"use client";

import { Search, Bell, UserCircle, LogOut } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export default function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="h-16 glass-panel border-b border-surface-border sticky top-0 z-10 flex items-center justify-between px-8">
      <div className="flex-1 max-w-xl">
        <div className="relative group">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-emerald-500 transition-colors" />
          <input 
            type="text" 
            placeholder="Buscar alunos, provas ou turmas..." 
            className="w-full bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
          />
        </div>
      </div>
      
      <div className="flex items-center space-x-4">
        <button className="p-2 text-slate-400 hover:text-emerald-500 transition-colors relative">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-surface"></span>
        </button>
        <div className="h-8 w-px bg-surface-border mx-2"></div>
        <button
          type="button"
          onClick={() => logout()}
          className="flex items-center space-x-2 text-sm font-medium hover:opacity-80 transition-opacity"
          title="Sair"
        >
          <UserCircle className="w-8 h-8 text-emerald-600" />
          <div className="text-left hidden sm:block">
            <p className="text-foreground leading-none">
              {user?.email?.split("@")[0] ?? "—"}
            </p>
            <span className="text-xs text-slate-500 capitalize">{user?.role ?? ""}</span>
          </div>
          <LogOut className="w-4 h-4 text-slate-400 hidden sm:block" aria-hidden />
        </button>
      </div>
    </header>
  );
}
