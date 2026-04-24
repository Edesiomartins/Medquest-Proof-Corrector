"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export type AuthUser = {
  id: string;
  email: string;
  role: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  token: string | null;
  bootstrapping: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = "access_token";
const USER_KEY = "user";

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [bootstrapping, setBootstrapping] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      const t =
        typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
      if (!t) {
        setToken(null);
        setUser(null);
        setBootstrapping(false);
        return;
      }
      setToken(t);
      try {
        const r = await api.get<AuthUser>("/auth/me");
        if (!cancelled) {
          setUser(r.data);
          localStorage.setItem(USER_KEY, JSON.stringify(r.data));
        }
      } catch {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        if (!cancelled) setToken(null);
      } finally {
        if (!cancelled) setBootstrapping(false);
      }
    }

    init();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const r = await api.post<{ access_token: string }>("/auth/login", {
      email,
      password,
    });
    localStorage.setItem(TOKEN_KEY, r.data.access_token);
    setToken(r.data.access_token);
    const me = await api.get<AuthUser>("/auth/me");
    setUser(me.data);
    localStorage.setItem(USER_KEY, JSON.stringify(me.data));
    router.replace("/");
  }, [router]);

  const register = useCallback(async (email: string, password: string) => {
    const r = await api.post<{ access_token: string }>("/auth/register", {
      email,
      password,
    });
    localStorage.setItem(TOKEN_KEY, r.data.access_token);
    setToken(r.data.access_token);
    const me = await api.get<AuthUser>("/auth/me");
    setUser(me.data);
    localStorage.setItem(USER_KEY, JSON.stringify(me.data));
    router.replace("/");
  }, [router]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({
      user,
      token,
      bootstrapping,
      login,
      register,
      logout,
    }),
    [user, token, bootstrapping, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
