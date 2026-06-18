import { getGtmContainerId, getGtmEnabled } from "src/envService";

/**
 * The GTM bootstrap event (`gtm.start` / `gtm.js`) is Google Tag Manager's own control event,
 * not one of our application `GTMEvent` types, so it is pushed with a localized cast.
 */
type GtmBootstrapEvent = { "gtm.start": number; event: "gtm.js" };

/**
 * Initializes Google Tag Manager at runtime from environment configuration.
 *
 * Replaces the previously hard-coded (and duplicated) GTM snippet in `public/index.html`,
 * so the container ID is per-environment via `FRONTEND_GTM_CONTAINER_ID` and can be turned
 * off entirely via `FRONTEND_GTM_ENABLED`. Mirrors how Sentry is initialized (see `sentryInit`).
 *
 * No-op (with a console hint) when GTM is disabled or no container ID is set.
 */
export function initGTM() {
  const enabled = getGtmEnabled().toLowerCase() === "true";
  const containerId = getGtmContainerId();

  if (!enabled) {
    console.info("GTM is not enabled. Google Tag Manager will not be initialized.");
    return;
  }

  if (!containerId) {
    console.warn("GTM is enabled but container ID is not set. Google Tag Manager will not be initialized.");
    return;
  }

  console.info("Initializing Google Tag Manager");

  // Initialize the dataLayer and push the GTM bootstrap event before injecting the script,
  // matching the behaviour of the official GTM snippet.
  window.dataLayer = window.dataLayer || [];
  (window.dataLayer as unknown as GtmBootstrapEvent[]).push({
    "gtm.start": new Date().getTime(),
    event: "gtm.js",
  });

  // Inject the GTM script.
  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(containerId)}`;
  document.head.appendChild(script);

  // Inject the GTM noscript fallback iframe.
  const noscript = document.createElement("noscript");
  const iframe = document.createElement("iframe");
  iframe.src = `https://www.googletagmanager.com/ns.html?id=${encodeURIComponent(containerId)}`;
  iframe.height = "0";
  iframe.width = "0";
  iframe.style.display = "none";
  iframe.style.visibility = "hidden";
  noscript.appendChild(iframe);
  document.body.insertBefore(noscript, document.body.firstChild);
}
