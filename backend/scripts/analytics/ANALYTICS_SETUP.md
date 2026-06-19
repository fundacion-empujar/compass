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

> **GTM tag schema gotcha (learned the hard way).** The config tag sets User-ID (and any other
> config setting) through the **`configSettingsTable`** parameter, whose map columns are
> **`parameter`** and **`parameterValue`** — *not* `fieldsToSet` / `fieldName`. Sending the wrong
> columns fails with `400 vendorTemplate.parameter.configSettingsTable[0].fieldName: Unknown column
> name`. GTM also silently upgrades the older `gaawc` ("GA4 Configuration") tag to the modern
> `googtag` ("Google Tag") on save (`measurementId`→`tagId`, `sendPageView`→`send_page_view`). The
> vendor-template schemas aren't in the public API docs, so **the reliable way to get any GTM tag
> body right is to read a known-working tag from a live container in the same account** and copy its
> structure (we derived this from dev's `GTM-W6CRXXRD`):
>
> ```python
> # read-only: dump a live tag's parameters to see the exact schema
> tm = build("tagmanager", "v2", credentials=creds)
> live = tm.accounts().containers().versions().live(parent="accounts/<ACCT>/containers/<ID>").execute()
> for t in live.get("tag", []):
>     print(t["name"], t["type"], t.get("parameter"))
> ```

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

> **Important — the `gtm` step is NOT idempotent.** `create_gtm_container` makes a **brand-new
> container every run**, so if the `gtm` step fails partway (e.g. a single tag 400s), do **not**
> re-run `--step gtm` — you'll end up with a duplicate, half-built container. Instead, **finish the
> existing container in place**: it already has its variables/triggers/event tags, so just add what's
> missing and publish. The GA4 property + measurement ID are preserved in the checkpoint, so never
> recreate them. Two ways to finish in place against `--gtm-container-path accounts/<ACCT>/containers/<ID>`:
> - `--step spa-tracking` then `--step publish` (if only SPA tracking + publish remain), or
> - a short script that imports the `gtm.py` helpers and calls the remaining
>   `create_gtm_*` functions + `publish_gtm_version` on the container's workspace.
>
> If you'd rather start clean, **delete the partial container first** (GTM Admin → Container →
> Remove), then re-run `--step gtm` + `--step publish`.

### Adding SPA Tracking to an Existing Container
```bash
python3 setup_analytics.py \
  --ga4-account-id <GA4_ACCOUNT_ID> --gtm-account-id <GTM_ACCOUNT_ID> \
  --url "https://brujula.compass.tabiya.tech" --credentials path/to/key.json \
  --step spa-tracking --gtm-container-path accounts/<GTM_ACCOUNT_ID>/containers/<CONTAINER_ID>
```
Then publish with `--step publish`.

## Mirroring a full container (`--rebuild` + `tracking_spec.json`)

Beyond the bootstrap above, the script can rebuild a container to match a **declarative spec**,
`backend/scripts/analytics/tracking_spec.json`. This is how prod's container was made to **mirror
dev's hand-built tracking** (button clicks, consent views, form submissions, report downloads) on top
of the code-driven events — reproducibly, leaving dev untouched.

`tracking_spec.json` is the source of truth: the full set of built-in variables, variables, triggers
and tags. Measurement IDs are **not** baked in — every tag references the `{{GA4 Measurement ID}}`
variable, which the builder sets to the target env's measurement ID, so the same spec reproduces on
any environment. The spec was generated by reading a live "golden" container (dev `GTM-W6CRXXRD`) via
the API and normalizing it (strip server ids, replace the literal measurement id with the
`{{GA4 Measurement ID}}` **variable reference**, reference triggers by name). To refresh it after
changing the golden container, re-dump dev and regenerate.

```bash
python3 setup_analytics.py --rebuild \
  --ga4-account-id <GA4_ACCOUNT_ID> --gtm-account-id <GTM_ACCOUNT_ID> \
  --url "https://brujula.compass.tabiya.tech" \
  --gtm-container-id GTM-XXXXXXX \
  --ga4-measurement-id G-XXXXXXXXXX \
  --credentials path/to/key.json \
  [--dry-run]
```

`--rebuild` **clears every tag, trigger and user variable** in the target container's default
workspace, then builds the full spec and publishes. It is **idempotent** (re-running yields an
identical container) and safe to re-run after a partial failure — the live/published version is only
replaced on the final `publish`, so a mid-run failure never breaks live tracking; it just leaves a
dirty workspace the next `--rebuild` clears. It keeps the container's public ID (no `env.js` /
Secret Manager re-wiring). **Always `--dry-run` first** — it prints the clear-vs-create diff.

### Lessons baked in (so they don't recur)
- **Measurement ID must be a variable reference or a literal.** A GA4 event tag's
  `measurementIdOverride` (and a Google Tag's `tagId`) must be `{{GA4 Measurement ID}}` **with braces**
  or a literal `G-XXXX`. A bare string `GA4 Measurement ID` is rejected with
  `400 … measurementIdOverride: Please enter a valid measurement ID`.
- **Enable the built-in variables.** Click/form triggers reference built-in variables (Click Element,
  Click Text, Form ID, …) which are **off by default**; the builder enables them
  (`built_in_variables.create`). Without them, click/form tags silently never fire (this had to be
  done by hand the first time).
- **Form-submission events come from GA4 Enhanced Measurement, not the frontend.** Triggers like
  `registration_form_submit` / `login_form_submit` fire on a `form_submit` dataLayer event that
  **gtag itself pushes** when Enhanced Measurement "Form interactions" is on (carrying
  `eventModel.form_destination`, which the `data_layer_form_destination` variable reads). No frontend
  code pushes `form_submit` — keep "Form interactions" enabled on the data stream or these won't fire.
- **Avoid double page_views.** The mirrored Google Tag has `send_page_view=false` added so it does NOT
  emit an automatic page_view that would duplicate the dedicated `GA4 Page View - SPA` tag (which sends
  the hash-normalized virtual URL). Dev's original Google Tag lacked this and double-counts.
- **DOM click selectors can be fragile.** The report-download triggers match a build-generated MUI
  class (`css-…-MuiTypography-root`) that changes between builds — prefer a stable `data-testid`. The
  other click triggers already match stable `data-testid` attributes.
- **Event names are dev's verbatim** (including the `click_registration_buttton` typo) so dev's
  existing GA4 dashboards apply to prod unchanged.

## CLI Reference

| Flag | Required | Description |
|------|----------|-------------|
| `--ga4-account-id` | Yes | GA4 account ID (numeric) |
| `--gtm-account-id` | Yes | GTM account ID (numeric) |
| `--url` | Yes | Deployed URL of the environment |
| `--credentials` | Yes | Path to service account JSON key file |
| `--checkpoint` | No | Resume checkpoint JSON (default: `analytics-setup.checkpoint.json`; NOT consumed by the app) |
| `--property-name` | No | GA4 property name (default: `Brújula`) |
| `--timezone` | No | GA4 reporting timezone, IANA name (default: `America/Argentina/Buenos_Aires`) |
| `--currency` | No | GA4 reporting currency — cosmetic, no revenue events (default: `USD`) |
| `--dry-run` | No | Validate inputs without creating resources |
| `--step` | No | Run only one step: `ga4`, `gtm`, `spa-tracking`, `publish` |
| `--rebuild` | No | Clear the target container and rebuild it from `--spec` (mirror mode; idempotent) |
| `--spec` | No | Path to `tracking_spec.json` (default: next to the script) |
| `--ga4-property-id` / `--ga4-measurement-id` / `--gtm-container-id` / `--gtm-container-path` | No | Existing IDs for `--step` resume / `--rebuild` |

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
- **`400 … configSettingsTable[0].fieldName: Unknown column name`** (on the GA4 Config tag) — the
  config tag's settings table uses `parameter` / `parameterValue` columns, not `fieldName` / `value`.
  This is already fixed in `gtm.py`; if you hit it after editing that tag, read a live tag to confirm
  the schema (see the "GTM tag schema gotcha" note above). The container is left partly built — see
  "Resuming After a Failure" to finish it in place rather than re-running `--step gtm`.
- **`400 … measurementIdOverride: Please enter a valid measurement ID`** — a tag's measurement field
  is a bare string instead of `{{GA4 Measurement ID}}` (with braces) or a literal `G-XXXX`. Check the
  spec normalization kept the braces.
- **Click/form tags never fire** — the container's built-in variables (Click Element, Form ID, …) are
  not enabled. `--rebuild` enables them; building by hand needs `built_in_variables.create`.
- **Form-submission events missing** — GA4 Enhanced Measurement "Form interactions" is off on the data
  stream; the `form_submit` dataLayer event those triggers need comes from gtag, not the app.
- **403 "insufficient authentication scopes"** — the service account needs GA4 **Editor** + GTM **Publish**.
- **Fails at publish** — resume with `--step publish --gtm-container-path accounts/XXX/containers/YYY`.
- **GTM not loading in the browser** — confirm `FRONTEND_GTM_ENABLED` is base64 of `"true"`
  (`dHJ1ZQ==`) and `FRONTEND_GTM_CONTAINER_ID` is set in `env.js`; check the console for
  "GTM is not enabled" / "container ID is not set"; check the Network tab for `googletagmanager.com`.
- **Events not in GA4** — use GTM Preview and GA4 DebugView; standard reports lag 24–48h.
