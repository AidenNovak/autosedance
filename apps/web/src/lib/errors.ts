export function humanizeError(
  t: (key: string, params?: Record<string, any>) => string,
  err: unknown,
  fallback: string
): string {
  if (err instanceof Error) {
    if (err.message === "AUTH_REQUIRED") return t("auth.err.auth_required");
    if (err.message === "INTERNAL_ERROR") return t("common.internal_error");
    return err.message;
  }
  return fallback;
}

