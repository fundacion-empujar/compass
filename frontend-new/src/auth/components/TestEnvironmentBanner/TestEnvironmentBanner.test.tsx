// silence chatty console
import "src/_test_utilities/consoleMock";

import { fireEvent, render, screen } from "src/_test_utilities/test-utils";
import TestEnvironmentBanner, {
  DATA_TEST_ID,
  DISMISSED_STORAGE_KEY,
  deriveRecommendedFrontendUrl,
} from "./TestEnvironmentBanner";
import { getBackendUrl, getTargetEnvironmentName } from "src/envService";

jest.mock("src/envService", () => ({
  // Defaults consumed transitively by providers in test-utils (theme, i18n, snackbar, etc.).
  getFirebaseAPIKey: jest.fn(() => "mock-api-key"),
  getFirebaseDomain: jest.fn(() => "mock-auth-domain"),
  getApplicationLoginCode: jest.fn(() => ""),
  getApplicationRegistrationCode: jest.fn(() => ""),
  getLoginCodeDisabled: jest.fn(() => "false"),
  getRegistrationDisabled: jest.fn(() => "false"),
  getRegistrationCodeDisabled: jest.fn(() => "false"),
  getMetricsEnabled: jest.fn(() => "true"),
  getMetricsConfig: jest.fn(() => ""),
  getCvUploadEnabled: jest.fn(() => "true"),
  getSocialAuthDisabled: jest.fn(() => "false"),
  getSupportedLocales: jest.fn(() => JSON.stringify([])),
  getDefaultLocale: jest.fn(() => "en-US"),
  // Functions exercised by this component.
  getBackendUrl: jest.fn(),
  getTargetEnvironmentName: jest.fn(),
}));

const mockGetBackendUrl = getBackendUrl as jest.Mock;
const mockGetTargetEnvironmentName = getTargetEnvironmentName as jest.Mock;

describe("TestEnvironmentBanner", () => {
  beforeEach(() => {
    sessionStorage.clear();
    mockGetBackendUrl.mockReset();
    mockGetTargetEnvironmentName.mockReset();
  });

  describe("deriveRecommendedFrontendUrl", () => {
    test("strips /api and replaces test- prefix with dev-", () => {
      expect(deriveRecommendedFrontendUrl("https://test-brujula.compass.tabiya.tech/api")).toBe(
        "https://dev-brujula.compass.tabiya.tech"
      );
    });

    test("returns null when host has no test- prefix (would link back to itself)", () => {
      expect(deriveRecommendedFrontendUrl("https://dev-brujula.compass.tabiya.tech/api")).toBeNull();
    });

    test("returns null when URL is not https", () => {
      expect(deriveRecommendedFrontendUrl("http://test-brujula.compass.tabiya.tech/api")).toBeNull();
    });
  });

  test("does not render on dev environment", () => {
    mockGetTargetEnvironmentName.mockReturnValue("dev-brujula");
    mockGetBackendUrl.mockReturnValue("https://dev-brujula.compass.tabiya.tech/api");

    render(<TestEnvironmentBanner />);

    expect(screen.queryByTestId(DATA_TEST_ID.BANNER)).toBeNull();
  });

  test("does not render on local development (empty env name)", () => {
    mockGetTargetEnvironmentName.mockReturnValue("");
    mockGetBackendUrl.mockReturnValue("");

    render(<TestEnvironmentBanner />);

    expect(screen.queryByTestId(DATA_TEST_ID.BANNER)).toBeNull();
  });

  test("renders banner on test environment with a link to the derived dev URL", () => {
    mockGetTargetEnvironmentName.mockReturnValue("test-brujula");
    mockGetBackendUrl.mockReturnValue("https://test-brujula.compass.tabiya.tech/api");

    render(<TestEnvironmentBanner />);

    const banner = screen.getByTestId(DATA_TEST_ID.BANNER);
    expect(banner).toBeInTheDocument();

    const link = screen.getByTestId(DATA_TEST_ID.LINK);
    expect(link).toHaveAttribute("href", "https://dev-brujula.compass.tabiya.tech");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("dismissing the banner stores the flag in sessionStorage and hides the banner", () => {
    mockGetTargetEnvironmentName.mockReturnValue("test-brujula");
    mockGetBackendUrl.mockReturnValue("https://test-brujula.compass.tabiya.tech/api");

    render(<TestEnvironmentBanner />);

    expect(screen.getByTestId(DATA_TEST_ID.BANNER)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CLOSE_BUTTON));

    expect(screen.queryByTestId(DATA_TEST_ID.BANNER)).toBeNull();
    expect(sessionStorage.getItem(DISMISSED_STORAGE_KEY)).toBe("true");
  });

  test("stays hidden when sessionStorage already has the dismissed flag", () => {
    mockGetTargetEnvironmentName.mockReturnValue("test-brujula");
    mockGetBackendUrl.mockReturnValue("https://test-brujula.compass.tabiya.tech/api");
    sessionStorage.setItem(DISMISSED_STORAGE_KEY, "true");

    render(<TestEnvironmentBanner />);

    expect(screen.queryByTestId(DATA_TEST_ID.BANNER)).toBeNull();
  });

  test("does not render when env name is test- but BACKEND_URL cannot be safely derived", () => {
    mockGetTargetEnvironmentName.mockReturnValue("test-brujula");
    mockGetBackendUrl.mockReturnValue("http://localhost:8080/api");

    render(<TestEnvironmentBanner />);

    expect(screen.queryByTestId(DATA_TEST_ID.BANNER)).toBeNull();
  });
});
