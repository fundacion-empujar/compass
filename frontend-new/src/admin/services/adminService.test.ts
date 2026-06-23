// silence chatty console
import "src/_test_utilities/consoleMock";

import { AdminService } from "src/admin/services/adminService";
import AuthenticationStateService from "src/auth/services/AuthenticationState.service";

jest.mock("src/envService", () => ({
  getBackendUrl: () => "https://backend.test",
}));

const GIVEN_TOKEN = "fake-firebase-token";

describe("AdminService", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(AuthenticationStateService.getInstance(), "getToken").mockReturnValue(GIVEN_TOKEN);
    global.fetch = jest.fn();
  });

  const mockOkJson = (body: object) =>
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => body });

  test("createRegistrationLink sends a Bearer header and no ?token= query", async () => {
    // GIVEN the backend returns a link
    mockOkJson({ registration_code: "0035cABC", link: "https://x", already_used: false });

    // WHEN the admin generates a registration link
    await AdminService.getInstance().createRegistrationLink("0035cABC");

    // THEN the request hits /admin/registration-links with a Bearer header and no token query param
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe("https://backend.test/admin/registration-links");
    expect(url).not.toContain("token=");
    expect((init.headers as Record<string, string>).Authorization).toBe(`Bearer ${GIVEN_TOKEN}`);
    expect(init.method).toBe("POST");
  });

  test("createSharedCode sends a Bearer header", async () => {
    mockOkJson({
      invitation_code: "grupo",
      invitation_type: "REGISTER",
      allowed_usage: 1,
      valid_from: "",
      valid_until: "",
      sensitive_personal_data_requirement: "NOT_AVAILABLE",
    });

    await AdminService.getInstance().createSharedCode({ invitation_code: "grupo", invitation_type: "REGISTER" });

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe("https://backend.test/admin/shared-codes");
    expect((init.headers as Record<string, string>).Authorization).toBe(`Bearer ${GIVEN_TOKEN}`);
  });

  test("exportRegistrations sends a Bearer header and returns the blob", async () => {
    const givenBlob = new Blob(["user_id\n"], { type: "text/csv" });
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true, blob: async () => givenBlob });

    const result = await AdminService.getInstance().exportRegistrations();

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe("https://backend.test/admin/registrations/export");
    expect((init.headers as Record<string, string>).Authorization).toBe(`Bearer ${GIVEN_TOKEN}`);
    expect(result).toBe(givenBlob);
  });

  test("omits the Authorization header when no token is present", async () => {
    // GIVEN no in-memory token
    jest.spyOn(AuthenticationStateService.getInstance(), "getToken").mockReturnValue(null);
    mockOkJson({ registration_code: "x", link: "y", already_used: false });

    // WHEN a call is made
    await AdminService.getInstance().createRegistrationLink("x");

    // THEN no Authorization header is sent (the backend will reject with 401 — fails closed)
    const [, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  test("throws a descriptive error on a non-ok response", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: async () => ({ detail: "Super-admin access required" }),
    });

    await expect(AdminService.getInstance().createRegistrationLink("x")).rejects.toThrow(
      /Super-admin access required/
    );
  });
});
