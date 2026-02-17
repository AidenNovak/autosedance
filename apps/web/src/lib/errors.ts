export function humanizeError(
  t: (key: string, params?: Record<string, any>) => string,
  err: unknown,
  fallback: string
): string {
  if (err instanceof Error) {
    if (err.message === "AUTH_REQUIRED") {
      // Let the topbar AuthWidget react and open the login prompt.
      try {
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event("autos:auth_required"));
        }
      } catch {
        // ignore
      }
      return t("auth.err.auth_required");
    }
    if (err.message === "INTERNAL_ERROR") return t("common.internal_error");
    return err.message;
  }
  return fallback;
}
