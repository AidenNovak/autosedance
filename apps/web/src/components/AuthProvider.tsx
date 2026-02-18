"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import type { AuthLoginIn, AuthMe, AuthRegisterIn, AuthRegisterOut } from "@/lib/api";
import { authLogin, authLogout, authMe, authRegister } from "@/lib/api";

type AuthContextValue = {
  me: AuthMe | null;
  loading: boolean;
  refresh: () => Promise<void>;
  register: (input: AuthRegisterIn) => Promise<AuthRegisterOut>;
  login: (input: AuthLoginIn) => Promise<AuthMe>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider(props: { children: React.ReactNode }) {
  const [me, setMe] = useState<AuthMe | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const m = await authMe();
      setMe(m);
    } catch {
      setMe({ authenticated: false, user_id: null, username: null, email: null });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const register = useCallback(async (input: AuthRegisterIn) => {
    const m = await authRegister(input);
    setMe(m);
    return m;
  }, []);

  const login = useCallback(async (input: AuthLoginIn) => {
    const m = await authLogin(input);
    setMe(m);
    return m;
  }, []);

  const logout = useCallback(async () => {
    await authLogout();
    setMe({ authenticated: false, user_id: null, username: null, email: null });
  }, []);

  const value = useMemo<AuthContextValue>(() => {
    return { me, loading, refresh, register, login, logout };
  }, [me, loading, refresh, register, login, logout]);

  return <AuthContext.Provider value={value}>{props.children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
