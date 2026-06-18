// mute and spy on console
import "src/_test_utilities/consoleMock";
// mock envService getters (getGtmEnabled -> "false", getGtmContainerId -> "" by default)
import "src/_test_utilities/envServiceMock";

import { getGtmContainerId, getGtmEnabled } from "src/envService";
import { initGTM } from "./gtmInit";

describe("initGTM", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // reset the DOM and dataLayer between tests
    document.head.innerHTML = "";
    document.body.innerHTML = "";
    delete (window as unknown as { dataLayer?: unknown }).dataLayer;
  });

  test("does nothing and logs when GTM is disabled", () => {
    // GIVEN GTM is disabled
    (getGtmEnabled as jest.Mock).mockReturnValue("false");
    (getGtmContainerId as jest.Mock).mockReturnValue("GTM-TEST123");

    // WHEN initGTM runs
    initGTM();

    // THEN no script is injected and the disabled message is logged
    expect(document.head.querySelector('script[src*="googletagmanager"]')).toBeNull();
    expect(console.info).toHaveBeenCalledWith("GTM is not enabled. Google Tag Manager will not be initialized.");
    expect(window.dataLayer).toBeUndefined();
  });

  test("does nothing and warns when enabled but container ID is missing", () => {
    // GIVEN GTM is enabled but no container ID is set
    (getGtmEnabled as jest.Mock).mockReturnValue("true");
    (getGtmContainerId as jest.Mock).mockReturnValue("");

    // WHEN initGTM runs
    initGTM();

    // THEN no script is injected and a warning is logged
    expect(document.head.querySelector('script[src*="googletagmanager"]')).toBeNull();
    expect(console.warn).toHaveBeenCalledWith(
      "GTM is enabled but container ID is not set. Google Tag Manager will not be initialized."
    );
  });

  test("initializes GTM when enabled with a valid container ID", () => {
    // GIVEN GTM is enabled with a valid container ID
    const givenContainerId = "GTM-TEST123";
    (getGtmEnabled as jest.Mock).mockReturnValue("true");
    (getGtmContainerId as jest.Mock).mockReturnValue(givenContainerId);

    // WHEN initGTM runs
    initGTM();

    // THEN the dataLayer is created and the gtm.js bootstrap event is pushed
    expect(window.dataLayer).toBeDefined();
    const bootstrap = window.dataLayer.find((item) => (item as { event?: string }).event === "gtm.js");
    expect(bootstrap).toBeDefined();

    // AND the GTM script is injected exactly once with the configured container ID
    const scripts = document.head.querySelectorAll('script[src*="googletagmanager.com/gtm.js"]');
    expect(scripts).toHaveLength(1);
    expect((scripts[0] as HTMLScriptElement).src).toContain(`id=${givenContainerId}`);

    // AND the noscript fallback iframe is injected with the configured container ID
    const noscript = document.body.firstChild as HTMLElement;
    expect(noscript.nodeName.toLowerCase()).toBe("noscript");
    expect(noscript.innerHTML).toContain(`googletagmanager.com/ns.html?id=${givenContainerId}`);

    expect(console.info).toHaveBeenCalledWith("Initializing Google Tag Manager");
  });

  test("URL-encodes the container ID in the injected script", () => {
    // GIVEN a container ID needing encoding
    (getGtmEnabled as jest.Mock).mockReturnValue("true");
    (getGtmContainerId as jest.Mock).mockReturnValue("GTM TEST&1");

    // WHEN initGTM runs
    initGTM();

    // THEN the script src is URL-encoded
    const script = document.head.querySelector('script[src*="googletagmanager.com/gtm.js"]') as HTMLScriptElement;
    expect(script.src).toContain("id=GTM%20TEST%261");
  });
});
