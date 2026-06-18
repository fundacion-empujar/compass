# Analytics Setup Guide (GA4 + GTM)

This guide walks through setting up Google Analytics 4 (GA4) and Google Tag Manager (GTM) for a
Brújula (Compass fork) environment. The process is largely automated by
`backend/scripts/analytics/setup_analytics.py`, but requires a few one-time manual steps first.

> **Scope note for this fork.** Unlike upstream Njila, this fork does **not** use a
> `config/default.json` + `inject-config.py` pipeline. The GTM container ID is delivered per
> environment via `iac/cfgs/.env.compass.<env>` → Secret Manager → `iac/frontend/prepare_frontend.py`
> → `env.js`. The script therefore **prints** the values to wire in; it does not write any config.

## How It Works

```
Frontend (React)
  src/services/analytics/gtmInit.ts ── initGTM() loads the GTM container at runtime (like Sentry)
  src/utils/analytics/gtmService.ts ── GTMService.track*() builds typed events
  src/services/analytics/dataLayer.ts ── pushToDataLayer() (PII-redacting) ──▶ window.dataLayer
        │
        ▼
  GTM Container (tags/triggers) ──▶ GA4 Property (reports/dashboards)
```

- **GTM** is injected into the frontend at runtime by `initGTM()` (not via `index.html`), reading
  `FRONTEND_GTM_ENABLED` / `FRONTEND_GTM_CONTAINER_ID` from the environment.
- **GTM tags** fire GA4 events when the app's `dataLayer.push()` calls match configured triggers.
- **GA4** receives the events and makes them available for reporting.
- This is separate from the existing `MetricsService` (operational metrics to MongoDB).

## Tracked Events

The script provisions a GTM trigger + GA4 event tag for each event this fork's frontend fires
(source of truth: `frontend-new/src/types/gtm.d.ts`):

| Event | Parameters | Where |
|-------|-----------|-------|
| `page_view` | `page_location` (hash-normalized virtual URL) | Automatic: initial load + every route navigation |
| `registration_complete` | `registration_code`, `auth_method` | After successful registration |
| `first_visit` | `registration_code`, `source` | On the registration landing visit |
| `chat_message_sent` | `message_count`, `conversation_phase`, `experiences_explored`, `session_id` | Each user message |
| `conversation_completed` | `message_count`, `experiences_explored`, `session_id` | When the conversation completes |
| `user_identity_set` | `user_id`, `identifier_type`, `registration_code`, `auth_state`, `source` | On login/identity resolution |
| `user_identity_cleared` | `auth_state` | On logout |

The GA4 Config tag maps GA4 **User-ID** to the `{{user_id}}` data layer variable (set by
`user_identity_set`); see `frontend-new/src/analytics/README.md`.

> **Note:** `first_visit` is also a GA4 automatic event name. We keep it because the app fires it
> explicitly; dedupe in GA4 if it causes double counting.

### SPA Page View Tracking (HashRouter)

The app uses React's `HashRouter`, so URLs look like `https://example.com/#/skills-interests`.
GA4's default page view only sees `/` as the path because the hash fragment is not part of the URL
path. The setup script handles this by creating:

1. **`Virtual Page URL` variable** — Custom JS that normalizes hash URLs into proper paths.
2. **`History Change - SPA Navigation` trigger** — fires on every hash change (route navigation).
3. **`GA4 Page View - SPA` tag** — sends `page_view` on initial load and every navigation, with
   `page_location` overridden to the virtual URL.

The GA4 Config tag has `sendPageView` disabled to avoid duplicate page views.

> **Important:** In the GA4 data stream settings, disable **"Page changes based on browser history
> events"** under Enhanced Measurement → Advanced Settings, so GA4 doesn't send its own (`/`-pathed)
> `page_view` events in addition to the ones from GTM.

## Prerequisites (One-Time Manual Steps)

### 1. Create a GA4 Account
Go to [analytics.google.com](https://analytics.google.com) and create an account. One account can
hold properties for all environments. (GA4 accounts are free and not tied to GCP billing.)

### 2. Create a GTM Account
Go to [tagmanager.google.com](https://tagmanager.google.com) and create an account. One account,
containers per environment. **Do NOT** manually create a container — the script creates one.

### 3. Create a GCP Service Account
The script authenticates with a GCP service account (not OAuth browser flow). In GCP Console →
IAM & Admin → Service Accounts, create one, then create and download a JSON key. No GCP roles are
needed (permissions are granted directly in GA4/GTM). Store the key securely and **never commit it**.

### 4. Enable Google APIs
In the GCP project (APIs & Services → Library), enable:
- **Google Analytics Admin API** (`analyticsadmin.googleapis.com`)
- **Tag Manager API** (`tagmanager.googleapis.com`)

### 5. Grant Permissions to the Service Account
Find the service account email (`name@project.iam.gserviceaccount.com`):
- **GA4**: analytics.google.com → Admin → Account Access Management → add the email with **Editor**.
- **GTM**: tagmanager.google.com → Admin → Account-level User Management → add the email with **Publish**.

### 6. Find Your Account IDs
- **GA4 Account ID**: GA4 → Admin → Account Settings → numeric ID at the top.
- **GTM Account ID**: GTM → Admin → numeric Account ID in the header.

## Running the Setup Script

> Only **prod** needs a new container in this fork (dev keeps its existing container, test is
> disabled — see "Wiring into environments" below). Confirm all prerequisites are met before a real
> run; start with `--dry-run`.

### Install Dependencies
```bash
cd backend/scripts/analytics
pip install -r requirements.txt   # google-api-python-client, google-auth (NOT app runtime deps)
```

### Dry Run (validate without creating resources)
```bash
python3 setup_analytics.py \
  --ga4-account-id <GA4_ACCOUNT_ID> \
  --gtm-account-id <GTM_ACCOUNT_ID> \
  --url "https://brujula.compass.tabiya.tech" \
  --credentials path/to/service_account_key.json \
  --dry-run
```

### Full Run
```bash
python3 setup_analytics.py \
  --ga4-account-id <GA4_ACCOUNT_ID> \
  --gtm-account-id <GTM_ACCOUNT_ID> \
  --url "https://brujula.compass.tabiya.tech" \
  --property-name "Brújula" \
  --credentials path/to/service_account_key.json
```

This will:
1. Create a GA4 property and web data stream.
2. Create a GTM container with: the GA4 Config tag (all pages, `sendPageView=false`, User-ID from
   `{{user_id}}`), a custom-event trigger + GA4 event tag for each event above, and SPA page view
   tracking (Virtual Page URL variable, History Change trigger, GA4 Page View tag).
3. Publish the GTM container.
4. **Print** the `FRONTEND_GTM_ENABLED` / `FRONTEND_GTM_CONTAINER_ID` values to wire into the env.

> **Post-setup:** Disable "Page changes based on browser history events" in the GA4 data stream's
> Enhanced Measurement → Advanced Settings to avoid duplicate page views.

### Resuming After a Failure
The script saves checkpoints to `--checkpoint` (default `analytics-setup.checkpoint.json` next to the
script) after each major step. Resume with `--step`:
```bash
python3 setup_analytics.py \
  --ga4-account-id <GA4_ACCOUNT_ID> \
  --gtm-account-id <GTM_ACCOUNT_ID> \
  --url "https://brujula.compass.tabiya.tech" \
  --credentials path/to/service_account_key.json \
  --step publish \
  --gtm-container-path accounts/<GTM_ACCOUNT_ID>/containers/<CONTAINER_ID>
```
Available steps: `ga4`, `gtm`, `spa-tracking`, `publish`.

### Adding SPA Tracking to an Existing Container
```bash
python3 setup_analytics.py \
  --ga4-account-id <GA4_ACCOUNT_ID> --gtm-account-id <GTM_ACCOUNT_ID> \
  --url "https://brujula.compass.tabiya.tech" --credentials path/to/key.json \
  --step spa-tracking --gtm-container-path accounts/<GTM_ACCOUNT_ID>/containers/<CONTAINER_ID>
```
Then publish with `--step publish`.

## CLI Reference

| Flag | Required | Description |
|------|----------|-------------|
| `--ga4-account-id` | Yes | GA4 account ID (numeric) |
| `--gtm-account-id` | Yes | GTM account ID (numeric) |
| `--url` | Yes | Deployed URL of the environment |
| `--credentials` | Yes | Path to service account JSON key file |
| `--checkpoint` | No | Resume checkpoint JSON (default: `analytics-setup.checkpoint.json`; NOT consumed by the app) |
| `--property-name` | No | GA4 property name (default: `Brújula`) |
| `--dry-run` | No | Validate inputs without creating resources |
| `--step` | No | Run only one step: `ga4`, `gtm`, `spa-tracking`, `publish` |
| `--ga4-property-id` / `--ga4-measurement-id` / `--gtm-container-id` / `--gtm-container-path` | No | Existing IDs for `--step` resume |

## Wiring into Environments

After a run, take the printed `GTM Container ID` and set the per-environment values in
`iac/cfgs/.env.compass.<env>` (which is pushed to **GCP Secret Manager** at deploy and injected into
`env.js` by `iac/frontend/prepare_frontend.py`):

```
FRONTEND_GTM_ENABLED=True
FRONTEND_GTM_CONTAINER_ID=GTM-XXXXXXX
```

Injection chain:
```
iac/cfgs/.env.compass.<env> → Secret Manager → prepare_frontend.py → env.js (base64)
  → envService.ts (getGtmEnabled / getGtmContainerId) → gtmInit.ts (initGTM)
```

### Per-environment topology (this fork)

| Env | `FRONTEND_GTM_ENABLED` | `FRONTEND_GTM_CONTAINER_ID` |
|-----|------------------------|-----------------------------|
| **dev-brujula** | `True` | `GTM-W6CRXXRD` (existing container, kept) |
| **test-brujula** | `False` | _(unset — analytics disabled)_ |
| **prod (brujula)** | `True` | new container provisioned by this script |

> These `.env.compass.*` files are gitignored secrets managed by the operator; set them in Secret
> Manager as part of the deploy. Removing the old hard-coded snippet means an env only tracks if its
> `FRONTEND_GTM_*` values are present — set dev's (`GTM-W6CRXXRD`) before/with the first deploy of
> this change so dev analytics doesn't break.

### Disabling analytics for an environment
Set `FRONTEND_GTM_ENABLED=False` (or leave `FRONTEND_GTM_CONTAINER_ID` empty). `initGTM()` skips
initialization entirely and logs an info message.

## Frontend Architecture

| File | Purpose |
|------|---------|
| `frontend-new/src/services/analytics/gtmInit.ts` | `initGTM()` — loads the GTM container at runtime |
| `frontend-new/src/services/analytics/gtmInit.test.ts` | Tests for `initGTM()` |
| `frontend-new/src/services/analytics/dataLayer.ts` | `pushToDataLayer()` (PII-redacting) |
| `frontend-new/src/utils/analytics/gtmService.ts` | `GTMService` — typed event builders |
| `frontend-new/src/analytics/identity.ts` | GA4 User-ID identity flow (`user_identity_set/cleared`) |
| `frontend-new/src/types/gtm.d.ts` | DataLayer event type definitions |
| `frontend-new/src/envService.ts` | `getGtmEnabled()` / `getGtmContainerId()` |
| `frontend-new/src/index.tsx` | Calls `initGTM()` at app startup |

### Event integration points

| Event | File | Call |
|-------|------|------|
| `first_visit` | `src/auth/pages/Register/Register.tsx` | `GTMService.trackRegistrationVisit(...)` |
| `registration_complete` (email) | `src/auth/pages/Register/Register.tsx` | `GTMService.trackRegistrationComplete("email", ...)` |
| `registration_complete` (google) | `src/auth/components/SocialAuth/SocialAuth.tsx` | `GTMService.trackRegistrationComplete("google", ...)` |
| `chat_message_sent` | `src/chat/Chat.tsx` | `GTMService.trackMessageSent(...)` |
| `conversation_completed` | `src/chat/Chat.tsx` | `GTMService.trackConversationCompleted(...)` |
| `user_identity_set` / `user_identity_cleared` | `src/analytics/identity.ts` | identity resolution / logout |

## Troubleshooting

- **"No access token in response"** — GA4/GTM APIs may not be enabled in the GCP project.
- **403 "insufficient authentication scopes"** — the service account needs GA4 **Editor** + GTM **Publish**.
- **Fails at publish** — resume with `--step publish --gtm-container-path accounts/XXX/containers/YYY`.
- **GTM not loading in the browser** — confirm `FRONTEND_GTM_ENABLED` is base64 of `"true"`
  (`dHJ1ZQ==`) and `FRONTEND_GTM_CONTAINER_ID` is set in `env.js`; check the console for
  "GTM is not enabled" / "container ID is not set"; check the Network tab for `googletagmanager.com`.
- **Events not in GA4** — use GTM Preview and GA4 DebugView; standard reports lag 24–48h.
