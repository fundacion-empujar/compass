## How to add a new language to Brújula

This guide covers adding a new language to both the backend and `frontend-new`. Use BCP-47 language tags (e.g., `en-GB`, `es-AR`) consistently.

### 1. Backend

1.  **Create Locale Files**:
    *   Copy `backend/app/i18n/locales/en-US/messages.json` to `backend/app/i18n/locales/<your-locale>/messages.json`.
    *   Translate the values, keeping keys and placeholders (e.g., `{end_date}`) identical.

2.  **Enable Language**:
    *   Add your locale code to the `BACKEND_SUPPORTED_LANGUAGES` JSON array in your backend `.env` file (e.g., `BACKEND_SUPPORTED_LANGUAGES='["en-US", "<your-locale>"]'`). This is what actually enables the language.
    *   Optionally set `BACKEND_DEFAULT_LOCALE` (a single locale, e.g., `BACKEND_DEFAULT_LOCALE=en-US`) if this language should be the default. It must be one of the supported languages.

3.  **Verify** (Optional):
    *   Run `poetry run pytest app/i18n/test_i18n.py` in the `backend` directory to check translation-key consistency across all supported locales.

### 2. Frontend (`frontend-new`)

1.  **Create Locale Files**:
    *   Copy `frontend-new/src/i18n/locales/en-GB/translation.json` to `frontend-new/src/i18n/locales/<your-locale>/translation.json`.
    *   Translate the values.

2.  **Register Locale**:
    *   Add your locale to the `Locale` enum in `frontend-new/src/i18n/constants.ts`.
    *   In `frontend-new/src/i18n/i18n.ts`, import your new `translation.json` and add it to the `resources` map, keyed by the `Locale` enum value (no lowercase variants — the map is keyed by the enum, not raw strings).
    *   Add a `questions-<your-locale>.json` file under `frontend-new/src/feedback/overallFeedback/feedbackForm/` and import it in `i18n.ts`. Every supported locale has one; a new locale without it will fail to load.

3.  **Update Language Menu**:
    *   In `frontend-new/src/i18n/languageContextMenu/LanguageContextMenu.tsx`, add a new menu item pointing to your locale.

4.  **Enable Configuration**:
    *   Update `public/data/env.js` (or your environment variable provider).
    *   Add the locale to `FRONTEND_SUPPORTED_LOCALES` (JSON array, base64 encoded).
    *   Update `FRONTEND_DEFAULT_LOCALE` if this should be the default (base64 encoded).

5.  **Verify** (Optional):
    *   Run `yarn test -- src/i18n/locales/locales.test.ts` in `frontend-new` to ensure key consistency.

### 3. Evaluation Tests

To test with a specific locale in python tests, use `CustomProvider`:

```python
from app.i18n.translation_service import get_i18n_manager
from app.i18n.locale_provider import CustomProvider

# ... inside your test ...
get_i18n_manager().set_locale(CustomProvider("es-AR"))
```

