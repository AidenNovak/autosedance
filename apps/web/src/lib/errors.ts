export function humanizeError(
  t: (key: string, params?: Record<string, any>) => string,
  err: unknown,
  fallback: string
): string {
  if (err instanceof Error) {
    if (err.message === "AUTH_REQUIRED") {
      return t("auth.err.auth_required");
    }
    if (err.message === "RL_LIMITED")
      return `${t("auth.err.rl_limited")} · ${t("overload.contact_x", { handle: "@logiclogic1223" })} · ${t(
        "overload.contact_other",
        { handle: "aiden_novak" }
      )}`;
    if (err.message === "OVERLOADED")
      return `${t("overload.body")} · ${t("overload.contact_x", { handle: "@logiclogic1223" })} · ${t(
        "overload.contact_other",
        { handle: "aiden_novak" }
      )}`;
    if (err.message === "INTERNAL_ERROR") return t("common.internal_error");
    return err.message;
  }
  return fallback;
}
