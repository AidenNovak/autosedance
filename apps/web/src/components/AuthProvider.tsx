"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import type { AuthMe } from "@/lib/api";
import { authLogout, authMe, authRequestCode, authVerifyCode } from "@/lib/api";

type AuthContextValue = {
  me: AuthMe | null;
  loading: boolean;
  refresh: () => Promise<void>;
  requestCode: (email: string) => Promise<void>;
  verifyCode: (email: string, code: string) => Promise<void>;
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
      setMe({ authenticated: false, email: null });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const requestCode = useCallback(
    async (email: string) => {
      await authRequestCode(email);
    },
    []
  );

  const verifyCode = useCallback(async (email: string, code: string) => {
    const m = await authVerifyCode(email, code);
    setMe(m);
  }, []);

  const logout = useCallback(async () => {
    await authLogout();
    setMe({ authenticated: false, email: null });
  }, []);

  const value = useMemo<AuthContextValue>(() => {
    return { me, loading, refresh, requestCode, verifyCode, logout };
  }, [me, loading, refresh, requestCode, verifyCode, logout]);

  return <AuthContext.Provider value={value}>{props.children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

