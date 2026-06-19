"""GTM API operations for creating containers, tags, triggers, and variables."""

import time

from googleapiclient.errors import HttpError

# GTM API has a rate limit of 0.25 QPS (1 request per 4 seconds)
GTM_API_DELAY_SECONDS = 4

# Custom events to track. These mirror the events this fork's frontend pushes to the
# dataLayer (see frontend-new/src/types/gtm.d.ts and src/utils/analytics/gtmService.ts).
# Note: `first_visit` is also a GA4 automatic event name; we keep it because the app fires it
# explicitly (operators may dedupe in GA4 if needed).
CUSTOM_EVENTS = [
    {
        "name": "registration_complete",
        "parameters": [
            {"key": "registration_code", "type": "template"},
            {"key": "auth_method", "type": "template"},
        ],
    },
    {
        "name": "first_visit",
        "parameters": [
            {"key": "registration_code", "type": "template"},
            {"key": "source", "type": "template"},
        ],
    },
    {
        "name": "chat_message_sent",
        "parameters": [
            {"key": "message_count", "type": "template"},
            {"key": "conversation_phase", "type": "template"},
            {"key": "experiences_explored", "type": "template"},
            {"key": "session_id", "type": "template"},
        ],
    },
    {
        "name": "conversation_completed",
        "parameters": [
            {"key": "message_count", "type": "template"},
            {"key": "experiences_explored", "type": "template"},
            {"key": "session_id", "type": "template"},
        ],
    },
    {
        "name": "user_identity_set",
        "parameters": [
            {"key": "user_id", "type": "template"},
            {"key": "identifier_type", "type": "template"},
            {"key": "registration_code", "type": "template"},
            {"key": "auth_state", "type": "template"},
            {"key": "source", "type": "template"},
        ],
    },
    {
        "name": "user_identity_cleared",
        "parameters": [
            {"key": "auth_state", "type": "template"},
        ],
    },
]


def create_gtm_container(tagmanager, account_id: str, container_name: str) -> dict:
    """Create a GTM web container."""
    print(f"\nCreating GTM container '{container_name}'...")
    body = {
        "name": container_name,
        "usageContext": ["web"],
    }
    container = tagmanager.accounts().containers().create(
        parent=f"accounts/{account_id}",
        body=body,
    ).execute()

    print(f"  Created container: {container['name']}")
    print(f"  Container ID: {container['publicId']}")
    return container


def get_default_workspace(tagmanager, container_path: str) -> dict:
    """Get the default workspace for a container."""
    time.sleep(GTM_API_DELAY_SECONDS)
    workspaces = tagmanager.accounts().containers().workspaces().list(
        parent=container_path,
    ).execute()

    workspace = workspaces["workspace"][0]
    print(f"  Using workspace: {workspace['name']}")
    return workspace


def create_gtm_variable(tagmanager, workspace_path: str, name: str, value: str) -> dict:
    """Create a constant variable in GTM."""
    time.sleep(GTM_API_DELAY_SECONDS)
    print(f"  Creating variable: {name}...")
    body = {
        "name": name,
        "type": "c",
        "parameter": [
            {"type": "template", "key": "value", "value": value},
        ],
    }
    return tagmanager.accounts().containers().workspaces().variables().create(
        parent=workspace_path,
        body=body,
    ).execute()


def create_gtm_custom_event_trigger(tagmanager, workspace_path: str, event_name: str) -> dict:
    """Create a custom event trigger in GTM."""
    time.sleep(GTM_API_DELAY_SECONDS)
    trigger_name = f"CE - {event_name}"
    print(f"  Creating trigger: {trigger_name}...")
    body = {
        "name": trigger_name,
        "type": "customEvent",
        "customEventFilter": [
            {
                "type": "equals",
                "parameter": [
                    {"type": "template", "key": "arg0", "value": "{{_event}}"},
                    {"type": "template", "key": "arg1", "value": event_name},
                ],
            }
        ],
    }
    return tagmanager.accounts().containers().workspaces().triggers().create(
        parent=workspace_path,
        body=body,
    ).execute()


def create_gtm_ga4_config_tag(tagmanager, workspace_path: str, measurement_id_var: str) -> dict:
    """Create a GA4 Configuration tag (Google Tag) that fires on all pages.

    Page view tracking is disabled here because the app uses HashRouter (URLs like /#/path),
    and GA4's default page_view only sees "/" as the path. Instead, page views are tracked
    by a separate tag that normalizes hash URLs into proper paths for GA4 reporting.
    See create_gtm_page_view_tag().

    The GA4 User-ID is set from the {{user_id}} Data Layer Variable (pushed by the app's
    `user_identity_set` event); see frontend-new/src/analytics/README.md.
    """
    time.sleep(GTM_API_DELAY_SECONDS)
    print("  Creating GA4 Config tag...")
    body = {
        "name": "GA4 Config",
        "type": "gaawc",
        "parameter": [
            {"type": "template", "key": "measurementId", "value": f"{{{{{measurement_id_var}}}}}"},
            {"type": "boolean", "key": "sendPageView", "value": "false"},
            # Map GA4 User-ID to the user_id dataLayer variable (set by user_identity_set).
            # The config tag's settings table is `configSettingsTable` with parameter/parameterValue
            # columns — verified against the live dev container (GTM-W6CRXXRD), which sets user_id
            # the same way. (An earlier fieldsToSet/fieldName encoding was rejected with HTTP 400.)
            {
                "type": "list",
                "key": "configSettingsTable",
                "list": [
                    {
                        "type": "map",
                        "map": [
                            {"type": "template", "key": "parameter", "value": "user_id"},
                            {"type": "template", "key": "parameterValue", "value": "{{user_id}}"},
                        ],
                    },
                ],
            },
        ],
        # Fire on All Pages (built-in trigger ID)
        "firingTriggerId": ["2147479553"],
    }
    return tagmanager.accounts().containers().workspaces().tags().create(
        parent=workspace_path,
        body=body,
    ).execute()


def create_gtm_virtual_page_url_variable(tagmanager, workspace_path: str) -> dict:
    """Create a Custom JavaScript variable that normalizes hash-based URLs.

    The app uses HashRouter, so URLs look like https://example.com/#/skills-interests.
    GA4 extracts page_path from page_location, but the hash fragment is not part of the URL path,
    so GA4 only ever sees "/". This variable converts the hash into a proper path:
      https://example.com/#/skills-interests → https://example.com/skills-interests
    """
    time.sleep(GTM_API_DELAY_SECONDS)
    print("  Creating Custom JS Variable: Virtual Page URL...")
    js_code = (
        "function() {"
        " var hash = window.location.hash;"
        " if (hash && hash.length > 1) {"
        " return window.location.origin + hash.substring(1);"
        " }"
        " return window.location.href;"
        " }"
    )
    body = {
        "name": "Virtual Page URL",
        "type": "jsm",
        "parameter": [
            {"type": "template", "key": "javascript", "value": js_code},
        ],
    }
    return tagmanager.accounts().containers().workspaces().variables().create(
        parent=workspace_path,
        body=body,
    ).execute()


def create_gtm_history_change_trigger(tagmanager, workspace_path: str) -> dict:
    """Create a History Change trigger that fires on hash-based route navigation."""
    time.sleep(GTM_API_DELAY_SECONDS)
    print("  Creating trigger: History Change - SPA Navigation...")
    body = {
        "name": "History Change - SPA Navigation",
        "type": "historyChange",
    }
    return tagmanager.accounts().containers().workspaces().triggers().create(
        parent=workspace_path,
        body=body,
    ).execute()


def create_gtm_page_view_tag(
    tagmanager, workspace_path: str, measurement_id_var: str, history_trigger_id: str
) -> dict:
    """Create a GA4 page_view event tag that fires on initial load and SPA navigation.

    Uses the Virtual Page URL variable to override page_location so that
    hash-based routes (/#/path) appear as proper paths (/path) in GA4 reports.
    """
    time.sleep(GTM_API_DELAY_SECONDS)
    print("  Creating tag: GA4 Page View (SPA)...")
    body = {
        "name": "GA4 Page View - SPA",
        "type": "gaawe",
        "parameter": [
            {"type": "template", "key": "eventName", "value": "page_view"},
            {"type": "template", "key": "measurementIdOverride", "value": f"{{{{{measurement_id_var}}}}}"},
            {
                "type": "list",
                "key": "eventParameters",
                "list": [
                    {
                        "type": "map",
                        "map": [
                            {"type": "template", "key": "name", "value": "page_location"},
                            {"type": "template", "key": "value", "value": "{{Virtual Page URL}}"},
                        ],
                    },
                ],
            },
        ],
        # Fire on All Pages (initial load) + History Change (SPA navigation)
        "firingTriggerId": ["2147479553", history_trigger_id],
    }
    return tagmanager.accounts().containers().workspaces().tags().create(
        parent=workspace_path,
        body=body,
    ).execute()


def create_gtm_ga4_event_tag(
    tagmanager, workspace_path: str, event_name: str,
    trigger_id: str, measurement_id_var: str, event_params: list
) -> dict:
    """Create a GA4 Event tag."""
    time.sleep(GTM_API_DELAY_SECONDS)
    tag_name = f"GA4 Event - {event_name}"
    print(f"  Creating tag: {tag_name}...")

    # Build event parameters list for the tag
    param_list: list[dict] = []
    for param in event_params:
        param_list.append({
            "type": "map",
            "map": [
                {"type": "template", "key": "name", "value": param["key"]},
                {"type": "template", "key": "value", "value": f"{{{{{param['key']}}}}}"},
            ],
        })

    parameters: list[dict] = [
        {"type": "template", "key": "eventName", "value": event_name},
        {"type": "template", "key": "measurementIdOverride", "value": f"{{{{{measurement_id_var}}}}}"},
    ]

    if param_list:
        parameters.append({
            "type": "list",
            "key": "eventParameters",
            "list": param_list,
        })

    body = {
        "name": tag_name,
        "type": "gaawe",
        "parameter": parameters,
        "firingTriggerId": [trigger_id],
    }
    return tagmanager.accounts().containers().workspaces().tags().create(
        parent=workspace_path,
        body=body,
    ).execute()


def create_gtm_data_layer_variables(tagmanager, workspace_path: str) -> None:
    """Create Data Layer Variables for event parameters."""
    # Collect all unique parameter keys across events
    created_vars = set()
    for event in CUSTOM_EVENTS:
        for param in event["parameters"]:
            param_key = param["key"]
            if param_key not in created_vars:
                time.sleep(GTM_API_DELAY_SECONDS)
                print(f"  Creating Data Layer Variable: {param_key}...")
                body = {
                    "name": param_key,
                    "type": "v",
                    "parameter": [
                        {"type": "integer", "key": "dataLayerVersion", "value": "2"},
                        {"type": "boolean", "key": "setDefaultValue", "value": "false"},
                        {"type": "template", "key": "name", "value": param_key},
                    ],
                }
                tagmanager.accounts().containers().workspaces().variables().create(
                    parent=workspace_path,
                    body=body,
                ).execute()
                created_vars.add(param_key)


def publish_gtm_version(tagmanager, workspace_path: str) -> dict:
    """Create and publish a GTM container version."""
    time.sleep(GTM_API_DELAY_SECONDS)
    print("\nPublishing GTM container version...")
    version = tagmanager.accounts().containers().workspaces().create_version(
        path=workspace_path,
        body={
            "name": "Initial analytics setup",
            "notes": "Automated GA4+GTM setup by setup_analytics.py",
        },
    ).execute()

    container_version = version.get("containerVersion", {})
    version_id = container_version.get("containerVersionId", "")

    # Extract the container path from the workspace path
    container_path = "/".join(workspace_path.split("/")[:4])

    time.sleep(GTM_API_DELAY_SECONDS)
    tagmanager.accounts().containers().versions().publish(
        path=f"{container_path}/versions/{version_id}",
    ).execute()

    print(f"  Published version {version_id}")
    return version


# ---------------------------------------------------------------------------
# Spec-driven build (mirror an entire container from tracking_spec.json)
# ---------------------------------------------------------------------------
# A built-in GTM trigger (e.g. All Pages = 2147479553) — referenced by numeric id, not by name.
_BUILTIN_TRIGGER_MIN = 2000000000


def _is_builtin_trigger(trigger_id) -> bool:
    return str(trigger_id).isdigit() and int(trigger_id) >= _BUILTIN_TRIGGER_MIN


def enable_builtin_variables(tagmanager, workspace_path: str, types: list) -> None:
    """Enable GTM built-in variables (Click Element, Form ID, ...) used by click/form triggers."""
    if not types:
        return
    time.sleep(GTM_API_DELAY_SECONDS)
    print(f"  Enabling {len(types)} built-in variables...")
    # Already-enabled types return 409; enable one-by-one so a partial set still succeeds.
    for t in types:
        try:
            tagmanager.accounts().containers().workspaces().built_in_variables().create(
                parent=workspace_path, type=t,
            ).execute()
            time.sleep(GTM_API_DELAY_SECONDS)
        except HttpError as e:
            if e.resp.status != 409:  # 409 = already enabled
                raise


def _create_variable_from_spec(tagmanager, workspace_path: str, var: dict) -> dict:
    time.sleep(GTM_API_DELAY_SECONDS)
    print(f"  Variable: {var['name']}")
    body = {k: var[k] for k in ("name", "type", "parameter", "formatValue") if k in var}
    return tagmanager.accounts().containers().workspaces().variables().create(
        parent=workspace_path, body=body,
    ).execute()


def _create_trigger_from_spec(tagmanager, workspace_path: str, trig: dict) -> dict:
    time.sleep(GTM_API_DELAY_SECONDS)
    print(f"  Trigger: {trig['name']} ({trig['type']})")
    body = {k: trig[k] for k in ("name", "type", "customEventFilter", "filter", "autoEventFilter") if k in trig}
    return tagmanager.accounts().containers().workspaces().triggers().create(
        parent=workspace_path, body=body,
    ).execute()


def _create_tag_from_spec(tagmanager, workspace_path: str, tag: dict, name_to_trigger_id: dict) -> dict:
    time.sleep(GTM_API_DELAY_SECONDS)
    print(f"  Tag: {tag['name']} ({tag['type']})")
    firing = [t if _is_builtin_trigger(t) else name_to_trigger_id[t] for t in tag.get("firingTriggerId", [])]
    body = {k: tag[k] for k in ("name", "type", "parameter", "tagFiringOption", "consentSettings") if k in tag}
    body["firingTriggerId"] = firing
    return tagmanager.accounts().containers().workspaces().tags().create(
        parent=workspace_path, body=body,
    ).execute()


def build_container_from_spec(tagmanager, workspace_path: str, spec: dict, measurement_id: str) -> None:
    """Build a full container (built-in vars + variables + triggers + tags) from a tracking_spec.json.

    Tags reference triggers by NAME (resolved to the freshly created ids here) and the GA4 measurement
    id via the `{{GA4 Measurement ID}}` constant variable, so the same spec reproduces on any env.
    """
    enable_builtin_variables(tagmanager, workspace_path, spec.get("builtInVariable", []))

    print("\n  Creating variables...")
    create_gtm_variable(tagmanager, workspace_path, "GA4 Measurement ID", measurement_id)
    for var in spec.get("variable", []):
        _create_variable_from_spec(tagmanager, workspace_path, var)

    print("\n  Creating triggers...")
    name_to_trigger_id = {}
    for trig in spec.get("trigger", []):
        created = _create_trigger_from_spec(tagmanager, workspace_path, trig)
        name_to_trigger_id[trig["name"]] = created["triggerId"]

    print("\n  Creating tags...")
    for tag in spec.get("tag", []):
        _create_tag_from_spec(tagmanager, workspace_path, tag, name_to_trigger_id)


def clear_container(tagmanager, workspace_path: str) -> dict:
    """Delete every tag, trigger and user-defined variable in the workspace (tags first).

    Returns the counts removed. Built-in variables are left enabled (re-enabling is idempotent).
    """
    ws = tagmanager.accounts().containers().workspaces()
    counts = {"tag": 0, "trigger": 0, "variable": 0}
    for kind, lister, key in (
        ("tag", ws.tags, "tag"),
        ("trigger", ws.triggers, "trigger"),
        ("variable", ws.variables, "variable"),
    ):
        items = lister().list(parent=workspace_path).execute().get(key, [])
        for item in items:
            time.sleep(GTM_API_DELAY_SECONDS)
            lister().delete(path=item["path"]).execute()
            counts[kind] += 1
        print(f"  Removed {counts[kind]} {kind}(s)")
    return counts
