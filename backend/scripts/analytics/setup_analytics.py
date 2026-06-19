#!/usr/bin/env python3
"""
Automated GA4 + GTM setup for Brújula (Compass fork).

Creates a GA4 property with a web data stream, a GTM container with tags/triggers/variables
for the events this app fires (see CUSTOM_EVENTS in gtm.py), publishes the GTM version, and
prints the generated container ID for wiring into the per-environment config.

Unlike the upstream Njila script, this does NOT write a config/default.json or run an
inject-config step (this fork injects frontend env via iac/frontend/prepare_frontend.py from
Secret Manager). Instead it prints the values to add to iac/cfgs/.env.compass.<env> and a
checkpoint file is used purely for resume-after-failure.

The script supports step-by-step execution via --step (ga4, gtm, spa-tracking, publish) to
allow resuming after partial failures. Checkpoints are saved to the --checkpoint file after
each major step.

Prerequisites:
  1. GA4 account created at analytics.google.com
  2. GTM account created at tagmanager.google.com
  3. Service account created in GCP project with JSON key downloaded
  4. Service account email added as Editor in GA4 and as Publisher in GTM
  5. Google Analytics Admin API and Tag Manager API enabled in GCP project

Usage:
  # Full run (all steps):
  python3 setup_analytics.py \\
    --ga4-account-id 123456789 \\
    --gtm-account-id 987654321 \\
    --url "https://brujula.compass.tabiya.tech" \\
    --credentials path/to/service_account_key.json

  # Resume from a specific step after failure:
  python3 setup_analytics.py \\
    --ga4-account-id 123456789 \\
    --gtm-account-id 987654321 \\
    --url "https://brujula.compass.tabiya.tech" \\
    --credentials path/to/service_account_key.json \\
    --step publish \\
    --gtm-container-path accounts/123/containers/456

Dependencies:
  pip install -r requirements.txt

For full documentation, see backend/scripts/analytics/ANALYTICS_SETUP.md
"""

import argparse
import json
import sys
import time
from pathlib import Path


try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Missing dependencies. Install with: pip install -r requirements.txt")
    sys.exit(1)

from ga4 import create_ga4_property, create_ga4_data_stream
from gtm import (
    GTM_API_DELAY_SECONDS,
    CUSTOM_EVENTS,
    create_gtm_container,
    get_default_workspace,
    create_gtm_variable,
    create_gtm_custom_event_trigger,
    create_gtm_ga4_config_tag,
    create_gtm_virtual_page_url_variable,
    create_gtm_history_change_trigger,
    create_gtm_page_view_tag,
    create_gtm_ga4_event_tag,
    create_gtm_data_layer_variables,
    publish_gtm_version,
    build_container_from_spec,
    clear_container,
)

SCOPES = [
    "https://www.googleapis.com/auth/analytics.edit",
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.edit.containerversions",
    "https://www.googleapis.com/auth/tagmanager.publish",
]

DEFAULT_PROPERTY_NAME = "Brújula"


def authenticate(credentials_path: str) -> service_account.Credentials:
    """Authenticate using a GCP service account key file."""
    if not credentials_path:
        print("Error: --credentials is required (path to service account JSON key file).")
        sys.exit(1)

    credentials_file = Path(credentials_path)
    if not credentials_file.exists():
        print(f"Error: Credentials file not found: {credentials_path}")
        sys.exit(1)

    print(f"Authenticating with service account: {credentials_path}")
    creds = service_account.Credentials.from_service_account_file(
        str(credentials_file),
        scopes=SCOPES,
    )
    print(f"  Service account: {creds.service_account_email}")
    return creds


def save_checkpoint(checkpoint_path: Path, updates: dict) -> None:
    """Persist the generated analytics IDs to the checkpoint file (for resume-after-failure)."""
    checkpoint = {}
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    if "analytics" not in checkpoint:
        checkpoint["analytics"] = {}

    checkpoint["analytics"].update(updates)
    checkpoint["analytics"]["enabled"] = True

    checkpoint_path.write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nSaved checkpoint to {checkpoint_path}")


def print_env_instructions(gtm_container_id: str, ga4_property_id: str, ga4_measurement_id: str) -> None:
    """Print the per-environment values to wire into iac/cfgs + Secret Manager."""
    print("\n" + "=" * 60)
    print("NEXT STEPS — wire the GTM container into the target environment")
    print("=" * 60)
    print("\nAdd to iac/cfgs/.env.compass.<env> (and push to Secret Manager via the deploy):\n")
    print("  FRONTEND_GTM_ENABLED=True")
    print(f"  FRONTEND_GTM_CONTAINER_ID={gtm_container_id}")
    print("\nFor reference (GA4 IDs, not consumed by the frontend):")
    print(f"  GA4 Property ID:    {ga4_property_id}")
    print(f"  GA4 Measurement ID: {ga4_measurement_id}")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    default_checkpoint = str(Path(__file__).parent / "analytics-setup.checkpoint.json")
    parser = argparse.ArgumentParser(
        description="Automated GA4 + GTM setup for Brújula (Compass fork)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 setup_analytics.py \\
    --ga4-account-id 123456789 \\
    --gtm-account-id 987654321 \\
    --url "https://brujula.compass.tabiya.tech" \\
    --credentials path/to/service_account_key.json

Prerequisites:
  1. Create a GA4 account at analytics.google.com
  2. Create a GTM account at tagmanager.google.com
  3. Create a service account in GCP and download the JSON key
  4. Add the service account email as Editor in GA4 and Publisher in GTM
  5. Enable Analytics Admin API and Tag Manager API in GCP
        """,
    )
    parser.add_argument("--ga4-account-id", required=True, help="GA4 account ID (numeric)")
    parser.add_argument("--gtm-account-id", required=True, help="GTM account ID (numeric)")
    parser.add_argument("--url", required=True, help="Deployed URL of the env (e.g., https://brujula.compass.tabiya.tech)")
    parser.add_argument(
        "--checkpoint", default=default_checkpoint,
        help="JSON file used to checkpoint generated IDs for resume (NOT consumed by the app)",
    )
    parser.add_argument("--credentials", required=True, help="Path to service account JSON key file")
    parser.add_argument("--property-name", default=None, help=f"GA4 property name (defaults to '{DEFAULT_PROPERTY_NAME}')")
    parser.add_argument(
        "--timezone", default="America/Argentina/Buenos_Aires",
        help="GA4 property reporting timezone (IANA name; default: America/Argentina/Buenos_Aires)",
    )
    parser.add_argument(
        "--currency", default="USD",
        help="GA4 property reporting currency (cosmetic — no revenue events tracked; default: USD)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without creating resources")
    parser.add_argument(
        "--step", default=None,
        choices=["ga4", "gtm", "spa-tracking", "publish"],
        help=(
            "Run only a specific step (uses IDs from the checkpoint for dependencies):\n"
            "  ga4          - Create GA4 property + data stream\n"
            "  gtm          - Create GTM container + tags/triggers/variables\n"
            "  spa-tracking - Add SPA page view tracking to an existing container\n"
            "  publish      - Publish the GTM container version"
        ),
    )
    # For --step=publish, allow passing existing IDs directly
    parser.add_argument("--ga4-property-id", default=None, help="Existing GA4 property ID (for --step resume)")
    parser.add_argument("--ga4-measurement-id", default=None, help="Existing GA4 measurement ID (for --step resume)")
    parser.add_argument("--gtm-container-id", default=None, help="Existing GTM container public ID, e.g. GTM-XXXXXXX (for --step resume)")
    parser.add_argument("--gtm-container-path", default=None, help="Existing GTM container path, e.g. accounts/123/containers/456 (for --step resume)")
    # Rebuild mode: clear an existing container and rebuild it from a tracking spec (mirrors dev).
    default_spec = str(Path(__file__).parent / "tracking_spec.json")
    parser.add_argument(
        "--rebuild", action="store_true",
        help="Clear the target container and rebuild it from --spec (idempotent; mirrors dev's tracking)",
    )
    parser.add_argument("--spec", default=default_spec, help="Path to tracking_spec.json (for --rebuild)")

    return parser.parse_args()


def get_ids_from_checkpoint(checkpoint: dict) -> dict:
    """Read existing analytics IDs from the checkpoint (used to resume)."""
    analytics = checkpoint.get("analytics", {})
    return {
        "ga4_property_id": analytics.get("ga4PropertyId", ""),
        "ga4_measurement_id": analytics.get("ga4MeasurementId", ""),
        "gtm_container_id": analytics.get("gtmContainerId", ""),
        "gtm_account_id": analytics.get("gtmAccountId", ""),
    }


def resolve_ids(args, checkpoint: dict) -> dict:
    """Resolve IDs from CLI args, falling back to the checkpoint file."""
    saved = get_ids_from_checkpoint(checkpoint)
    return {
        "ga4_property_id": args.ga4_property_id or saved["ga4_property_id"],
        "ga4_measurement_id": args.ga4_measurement_id or saved["ga4_measurement_id"],
        "gtm_container_id": args.gtm_container_id or saved["gtm_container_id"],
        "gtm_container_path": args.gtm_container_path or "",
    }


def step_ga4(
    analytics_admin, account_id: str, property_name: str, url: str,
    time_zone: str, currency_code: str,
) -> tuple:
    """Run GA4 setup: create property + data stream. Returns (property_id, measurement_id)."""
    print("\n" + "=" * 60)
    print("STEP: GA4 — Create property and data stream")
    print("=" * 60)

    ga4_property = create_ga4_property(analytics_admin, account_id, property_name, time_zone, currency_code)
    property_resource_name = ga4_property["name"]
    property_id = property_resource_name.split("/")[-1]

    data_stream = create_ga4_data_stream(analytics_admin, property_resource_name, url, property_name)
    measurement_id = data_stream.get("webStreamData", {}).get("measurementId", "")

    print(f"\n  [OK] GA4 Property ID: {property_id}")
    print(f"  [OK] Measurement ID: {measurement_id}")
    return property_id, measurement_id


def step_gtm(tagmanager, account_id: str, container_name: str, measurement_id: str) -> tuple:
    """Run GTM setup: create container + tags/triggers/variables. Returns (container_public_id, container_path, workspace_path)."""
    print("\n" + "=" * 60)
    print("STEP: GTM — Create container, tags, triggers, variables")
    print("=" * 60)

    gtm_container = create_gtm_container(tagmanager, account_id, container_name)
    gtm_container_id = gtm_container["publicId"]
    container_path = gtm_container["path"]

    print("\n  Getting workspace...")
    workspace = get_default_workspace(tagmanager, container_path)
    workspace_path = workspace["path"]

    measurement_id_var_name = "GA4 Measurement ID"
    print("\n  Creating GTM variables...")
    create_gtm_variable(tagmanager, workspace_path, measurement_id_var_name, measurement_id)
    create_gtm_data_layer_variables(tagmanager, workspace_path)

    print("\n  Creating GTM triggers and event tags...")
    for event in CUSTOM_EVENTS:
        trigger = create_gtm_custom_event_trigger(tagmanager, workspace_path, event["name"])
        trigger_id = trigger["triggerId"]
        create_gtm_ga4_event_tag(
            tagmanager, workspace_path, event["name"],
            trigger_id, measurement_id_var_name, event["parameters"],
        )

    print("\n  Creating GA4 Config tag...")
    create_gtm_ga4_config_tag(tagmanager, workspace_path, measurement_id_var_name)

    print("\n  Setting up SPA (HashRouter) page view tracking...")
    create_gtm_virtual_page_url_variable(tagmanager, workspace_path)
    history_trigger = create_gtm_history_change_trigger(tagmanager, workspace_path)
    history_trigger_id = history_trigger["triggerId"]
    create_gtm_page_view_tag(tagmanager, workspace_path, measurement_id_var_name, history_trigger_id)

    print(f"\n  [OK] GTM Container ID: {gtm_container_id}")
    print(f"  [OK] Container path: {container_path}")
    print(f"  [OK] Workspace path: {workspace_path}")
    return gtm_container_id, container_path, workspace_path


def step_spa_tracking(tagmanager, container_path: str, measurement_id: str) -> None:
    """Add SPA (HashRouter) page view tracking to an existing GTM container."""
    print("\n" + "=" * 60)
    print("STEP: SPA-TRACKING — Add hash-based page view tracking")
    print("=" * 60)

    print(f"\n  Looking up workspace for container: {container_path}")
    workspace = get_default_workspace(tagmanager, container_path)
    workspace_path = workspace["path"]

    measurement_id_var_name = "GA4 Measurement ID"

    # Check if the measurement ID variable already exists, create if not
    time.sleep(GTM_API_DELAY_SECONDS)
    existing_vars = tagmanager.accounts().containers().workspaces().variables().list(
        parent=workspace_path,
    ).execute()
    var_names = [v["name"] for v in existing_vars.get("variable", [])]
    if measurement_id_var_name not in var_names:
        print("\n  Measurement ID variable not found, creating it...")
        create_gtm_variable(tagmanager, workspace_path, measurement_id_var_name, measurement_id)
    else:
        print("\n  Measurement ID variable already exists, skipping...")

    print("\n  Creating SPA page view tracking resources...")
    create_gtm_virtual_page_url_variable(tagmanager, workspace_path)
    history_trigger = create_gtm_history_change_trigger(tagmanager, workspace_path)
    history_trigger_id = history_trigger["triggerId"]
    create_gtm_page_view_tag(tagmanager, workspace_path, measurement_id_var_name, history_trigger_id)

    print(f"\n  [OK] SPA tracking added to container: {container_path}")
    print("  Note: You must publish the container for changes to take effect.")
    print("  Run with --step=publish --gtm-container-path=... to publish.")


def step_publish(tagmanager, container_path: str) -> None:
    """Publish the GTM container version."""
    print("\n" + "=" * 60)
    print("STEP: PUBLISH — Create and publish GTM container version")
    print("=" * 60)

    # Find the workspace
    print(f"\n  Looking up workspace for container: {container_path}")
    workspace = get_default_workspace(tagmanager, container_path)
    workspace_path = workspace["path"]

    publish_gtm_version(tagmanager, workspace_path)
    print("\n  [OK] GTM container published")


def resolve_container_path(tagmanager, account_id: str, container_public_id: str) -> str:
    """Look up a container's resource path from its public id (e.g. GTM-XXXXXXX)."""
    if not container_public_id:
        print("Error: --rebuild needs --gtm-container-id (e.g. GTM-XXXXXXX) or --gtm-container-path.")
        sys.exit(1)
    containers = tagmanager.accounts().containers().list(
        parent=f"accounts/{account_id}",
    ).execute().get("container", [])
    for container in containers:
        if container.get("publicId") == container_public_id:
            return container["path"]
    print(f"Error: container {container_public_id} not found in account {account_id}.")
    sys.exit(1)


def step_rebuild(tagmanager, container_path: str, spec: dict, measurement_id: str, dry_run: bool) -> None:
    """Clear the target container and rebuild it from the tracking spec (mirrors dev's tracking)."""
    print("\n" + "=" * 60)
    print("STEP: REBUILD — clear container and rebuild from spec")
    print("=" * 60)

    workspace = get_default_workspace(tagmanager, container_path)
    workspace_path = workspace["path"]
    ws = tagmanager.accounts().containers().workspaces()
    cur_tags = ws.tags().list(parent=workspace_path).execute().get("tag", [])
    cur_trigs = ws.triggers().list(parent=workspace_path).execute().get("trigger", [])
    cur_vars = ws.variables().list(parent=workspace_path).execute().get("variable", [])

    print(f"\n  Container:    {container_path}")
    print(f"  Measurement:  {measurement_id}")
    print(f"  Currently:    {len(cur_tags)} tags, {len(cur_trigs)} triggers, {len(cur_vars)} variables")
    print(f"  Spec:         {len(spec['tag'])} tags, {len(spec['trigger'])} triggers, "
          f"{len(spec['variable']) + 1} variables, {len(spec.get('builtInVariable', []))} built-in variables")

    if dry_run:
        print("\n[DRY RUN] Would clear the above, then create these tags:")
        for tag in spec["tag"]:
            event_name = next((p["value"] for p in tag["parameter"] if p.get("key") == "eventName"), tag["type"])
            print(f"    - {tag['name']}  ->  {event_name}")
        print("\n[DRY RUN] Nothing was changed.")
        return

    print("\n  Clearing existing container contents...")
    clear_container(tagmanager, workspace_path)
    build_container_from_spec(tagmanager, workspace_path, spec, measurement_id)
    publish_gtm_version(tagmanager, workspace_path)
    print("\n  [OK] Container rebuilt and published")


def main():
    """Run the GA4 + GTM setup (all steps, or a single --step) and print the env values to wire in."""
    args = parse_args()

    checkpoint_path = Path(args.checkpoint)
    checkpoint = {}
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    # --- Rebuild mode (clear + rebuild a container from the tracking spec) ---
    if args.rebuild:
        creds = authenticate(args.credentials)
        tagmanager = build("tagmanager", "v2", credentials=creds)
        container_path = args.gtm_container_path or resolve_container_path(
            tagmanager, args.gtm_account_id, args.gtm_container_id,
        )
        measurement_id = args.ga4_measurement_id or resolve_ids(args, checkpoint)["ga4_measurement_id"]
        if not measurement_id:
            print("Error: --rebuild needs a measurement id (--ga4-measurement-id or a saved checkpoint).")
            sys.exit(1)
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        try:
            step_rebuild(tagmanager, container_path, spec, measurement_id, args.dry_run)
        except HttpError as e:
            print(f"\n[ERROR] API Error: {e}")
            print(f"Details: {e.content.decode()}")
            sys.exit(1)
        return

    property_name = args.property_name or DEFAULT_PROPERTY_NAME
    step = args.step

    print(f"Setting up analytics for '{property_name}'")
    print(f"  GA4 Account:  {args.ga4_account_id}")
    print(f"  GTM Account:  {args.gtm_account_id}")
    print(f"  URL:          {args.url}")
    print(f"  Timezone:     {args.timezone}")
    print(f"  Currency:     {args.currency}")
    print(f"  Checkpoint:   {checkpoint_path}")
    print(f"  Step:         {step or 'all'}")

    if args.dry_run:
        print("\n[DRY RUN] Would create:")
        print(f"  - GA4 property '{property_name}' ({args.timezone}, {args.currency}) with web data stream for {args.url}")
        print(f"  - GTM container '{property_name}' with:")
        for event in CUSTOM_EVENTS:
            params = ", ".join(p["key"] for p in event["parameters"])
            print(f"    - Event: {event['name']} (params: {params})")
        print("  - GA4 Config tag (all pages, sendPageView=false, User-ID from {{user_id}})")
        print("  - SPA page view tracking (HashRouter support):")
        print("    - Custom JS Variable: Virtual Page URL (normalizes hash URLs)")
        print("    - History Change trigger for SPA navigation")
        print("    - GA4 Page View tag (fires on all pages + history changes)")
        print("  - Would print FRONTEND_GTM_* values to add to iac/cfgs + Secret Manager")
        return

    # Authenticate
    creds = authenticate(args.credentials)

    # Resolve any existing IDs from the checkpoint or CLI args
    ids = resolve_ids(args, checkpoint)

    # Build API clients as needed
    tagmanager = None
    property_id = ""
    measurement_id = ""
    gtm_container_id = ""
    container_path = ""

    try:
        # --- GA4 step ---
        if step in (None, "ga4"):
            analytics_admin = build("analyticsadmin", "v1beta", credentials=creds)
            property_id, measurement_id = step_ga4(
                analytics_admin, args.ga4_account_id, property_name, args.url,
                args.timezone, args.currency,
            )
            # Save checkpoint immediately
            save_checkpoint(checkpoint_path, {
                "ga4AccountId": args.ga4_account_id,
                "ga4PropertyId": property_id,
                "ga4MeasurementId": measurement_id,
                "gtmAccountId": args.gtm_account_id,
            })
            print("\n  [CHECKPOINT] GA4 IDs saved")
            # Reload checkpoint for next steps
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            ids = resolve_ids(args, checkpoint)
        else:
            property_id = ids["ga4_property_id"]
            measurement_id = ids["ga4_measurement_id"]
            if not measurement_id:
                print("Error: No GA4 measurement ID found. Run --step=ga4 first or pass --ga4-measurement-id.")
                sys.exit(1)
            print(f"\n  [SKIP] GA4 — using existing Measurement ID: {measurement_id}")

        # --- GTM step ---
        if step in (None, "gtm"):
            tagmanager = build("tagmanager", "v2", credentials=creds)
            gtm_container_id, container_path, _ = step_gtm(
                tagmanager, args.gtm_account_id, property_name, measurement_id,
            )
            # Save checkpoint immediately
            save_checkpoint(checkpoint_path, {
                "ga4AccountId": args.ga4_account_id,
                "ga4PropertyId": property_id,
                "ga4MeasurementId": measurement_id,
                "gtmAccountId": args.gtm_account_id,
                "gtmContainerId": gtm_container_id,
            })
            print("\n  [CHECKPOINT] GTM IDs saved")
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            ids = resolve_ids(args, checkpoint)
        else:
            gtm_container_id = ids["gtm_container_id"]
            container_path = ids.get("gtm_container_path") or args.gtm_container_path or ""
            if step == "publish" and not container_path:
                print("Error: No GTM container path found. Pass --gtm-container-path (e.g. accounts/123/containers/456).")
                sys.exit(1)
            if gtm_container_id:
                print(f"\n  [SKIP] GTM — using existing Container ID: {gtm_container_id}")

        # --- SPA tracking step (standalone) ---
        if step == "spa-tracking":
            if tagmanager is None:
                tagmanager = build("tagmanager", "v2", credentials=creds)
            container_path = args.gtm_container_path or ""
            if not container_path:
                print("Error: --gtm-container-path is required for --step=spa-tracking.")
                sys.exit(1)
            step_spa_tracking(tagmanager, container_path, measurement_id)

        # --- Publish step ---
        if step in (None, "publish"):
            if tagmanager is None:
                tagmanager = build("tagmanager", "v2", credentials=creds)
            if not container_path:
                print("Error: No GTM container path. Pass --gtm-container-path (e.g. accounts/123/containers/456).")
                sys.exit(1)
            step_publish(tagmanager, container_path)

        print("\n" + "=" * 60)
        print(f"{'Step' if step else 'Setup'} complete!")
        print(f"  GA4 Property ID:    {property_id}")
        print(f"  GA4 Measurement ID: {measurement_id}")
        print(f"  GTM Container ID:   {gtm_container_id}")
        print("=" * 60)

        # Print the values to wire into the environment (replaces Njila's config/inject step).
        if gtm_container_id:
            print_env_instructions(gtm_container_id, property_id, measurement_id)

    except HttpError as e:
        print(f"\n[ERROR] API Error: {e}")
        print(f"Details: {e.content.decode()}")
        print("\nTip: Check the checkpoint file for saved IDs. Resume with --step=<step>")
        sys.exit(1)


if __name__ == "__main__":
    main()
