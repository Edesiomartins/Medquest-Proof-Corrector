"use client";

import { UserCircle, LogOut } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export default function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="h-16 glass-panel border-b border-surface-border sticky top-0 z-10 flex items-center justify-end px-8">
      <div className="flex items-center space-x-4">
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
