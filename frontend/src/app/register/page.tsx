"use client";

import axios from "axios";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { Eye, EyeOff } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const { bootstrapping, token, register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!bootstrapping && token) router.replace("/");
  }, [bootstrapping, token, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("A senha deve ter pelo menos 8 caracteres.");
      return;
    }
    setSubmitting(true);
    try {
      await register(email.trim(), password);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        const d = err.response?.data?.detail;
        setError(
          typeof d === "string"
            ? d
            : "Não foi possível cadastrar. O e-mail pode já estar em uso."
        );
      } else {
        setError("Erro inesperado. Tente novamente.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (bootstrapping) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500">
        Carregando…
      </div>
    );
  }

  if (token) return null;

  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="w-full max-w-md glass-panel rounded-2xl p-8 shadow-lg">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-lg bg-emerald-500 flex items-center justify-center text-white font-bold text-xl shadow-md shadow-emerald-500/20">
            M
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Criar conta</h1>
            <p className="text-sm text-slate-500">Professor — acesso ao corrector</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
              E-mail
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-surface-border bg-(--surface) px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
              Senha (mín. 8 caracteres)
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-surface-border bg-(--surface) px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="btn-primary w-full py-2.5 disabled:opacity-60"
          >
            {submitting ? "Criando…" : "Cadastrar"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Já tem conta?{" "}
          <Link href="/login" className="text-emerald-600 font-medium hover:underline">
            Entrar
          </Link>
        </p>
      </div>
    </div>
  );
}
