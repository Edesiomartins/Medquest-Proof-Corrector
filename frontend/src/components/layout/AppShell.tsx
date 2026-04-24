"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "@/contexts/AuthContext";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";

const PUBLIC_PATHS = new Set(["/login", "/register"]);

function AuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { bootstrapping, token } = useAuth();

  useEffect(() => {
    if (bootstrapping) return;
    if (!token) router.replace("/login");
  }, [bootstrapping, token, router]);

  if (bootstrapping) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500">
        Carregando…
      </div>
    );
  }

  if (!token) return null;

  return <>{children}</>;
}

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isPublic = pathname ? PUBLIC_PATHS.has(pathname) : false;

  if (isPublic) {
    return (
      <div className="min-h-screen flex flex-col bg-[var(--background)]">
        {children}
      </div>
    );
  }

  return (
    <AuthGate>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 ml-64 flex flex-col min-h-screen">
          <Header />
          <main className="flex-1 p-8 max-w-7xl mx-auto w-full">{children}</main>
        </div>
      </div>
    </AuthGate>
  );
}
