"use client";

import React, { createContext, useContext, useMemo, useState } from "react";

import type { Locale, Messages } from "@/i18n";
import { getMessages, t as translate } from "@/i18n";

type I18nContextValue = {
  locale: Locale;
  messages: Messages;
  t: (key: string, params?: Record<string, any>) => string;
  setLocale: (locale: Locale) => void;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider(props: {
  initialLocale: Locale;
  initialMessages: Messages;
  children: React.ReactNode;
}) {
  const [locale, setLocale] = useState<Locale>(props.initialLocale);
  const messages = useMemo(() => getMessages(locale), [locale]);

  const value = useMemo<I18nContextValue>(() => {
    return {
      locale,
      messages,
      t: (key: string, params?: Record<string, any>) => translate(messages, key, params),
      setLocale
    };
  }, [locale, messages]);

  return <I18nContext.Provider value={value}>{props.children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within <I18nProvider>");
  return ctx;
}

