# Translations (UI + Model Prompts)

This repo stores two kinds of i18n resources:

1. **Web UI messages** (JSON)
2. **Model prompt templates** (plain text, per locale)

The goal is:
- stable keys / stable placeholders
- easy to correct text (in Git)
- easy to add a new language
- validation to prevent missing keys or placeholder drift

## Web UI (Next.js)

**Location**
- `apps/web/src/i18n/locales/*.json`

**Runtime**
- The current locale is stored in cookie `autos_lang`.
- The UI uses `apps/web/src/i18n/index.ts` + `apps/web/src/components/I18nProvider.tsx`.

**Add / update translations**
1. Edit the target locale JSON file.
2. Keep keys identical across locales.
3. Keep `{placeholders}` identical per key across locales.

## Model Prompts (Backend)

**Location**
- `src/autosedance/prompts/i18n/<locale>/`

Each locale directory contains:
- `scriptwriter_system.txt`, `scriptwriter_user.txt`
- `segmenter_system.txt`, `segmenter_user.txt`
- `analyzer_system.txt`, `analyzer_user.txt`

**Runtime**
- Prompts are loaded by `src/autosedance/prompts/loader.py`.
- Jobs can pass `locale` in the job payload; worker uses it to select prompt language.
- If `locale` is missing, backend defaults to `zh-CN` (to preserve legacy behavior).

**Important**
- These templates are formatted with Python `str.format(...)`.
- If you need literal JSON braces in templates, use doubled braces: `{{` and `}}`.
- Keep placeholders identical across locales (example: `{total_duration}`, `{segment_duration}`, `{user_prompt}`, `{feedback}`, etc).

## Validation

Run:
```bash
python3 scripts/i18n_check.py
```

Checks:
- UI: same keys across locale JSON files, and same placeholder sets per key.
- Prompts: all expected prompt files exist per locale, and placeholders match the base locale.

## Adding A New Language

1. UI
   - Add `apps/web/src/i18n/locales/<locale>.json` (copy from `en.json` first).
   - Add the locale to `SUPPORTED_LOCALES` in `apps/web/src/i18n/index.ts`.
2. Prompts
   - Add `src/autosedance/prompts/i18n/<locale>/` with the 6 prompt files (copy from `en/` first).
   - Update `normalize_locale(...)` in `src/autosedance/prompts/loader.py` so your locale tag resolves correctly.
3. Run `python3 scripts/i18n_check.py` and fix any missing keys/placeholders.

