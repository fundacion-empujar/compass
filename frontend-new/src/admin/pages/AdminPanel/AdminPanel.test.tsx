// silence chatty console
import "src/_test_utilities/consoleMock";
// Mock Sentry
import "src/_test_utilities/sentryMock";
// Mock envService (getBackendUrl, getSupportedLocales, ...)
import "src/_test_utilities/envServiceMock";

import React from "react";
import { render, screen, fireEvent, waitFor } from "src/_test_utilities/test-utils";
import AdminPanel, { DATA_TEST_ID } from "src/admin/pages/AdminPanel/AdminPanel";
import { DATA_TEST_ID as LINK_TOOL_TEST_ID } from "src/admin/components/GenerateLinkTool/GenerateLinkTool";
import { DATA_TEST_ID as SHARED_TOOL_TEST_ID } from "src/admin/components/CreateSharedCodeTool/CreateSharedCodeTool";
import { DATA_TEST_ID as EXPORT_TOOL_TEST_ID } from "src/admin/components/ExportRegistrationsTool/ExportRegistrationsTool";
import { DATA_TEST_ID as REPORT_LOOKUP_TOOL_TEST_ID } from "src/admin/components/ReportLookupTool/ReportLookupTool";
import { DATA_TEST_ID as GENERAL_FAQ_TOOL_TEST_ID } from "src/admin/components/GeneralFaqTool/GeneralFaqTool";
import { DATA_TEST_ID as ERROR_PAGE_TEST_ID } from "src/error/errorPage/ErrorPage";

const mockCreateRegistrationLink = jest.fn();
const mockCreateSharedCode = jest.fn();
const mockExportRegistrations = jest.fn();

jest.mock("src/admin/services/adminService", () => ({
  AdminService: {
    getInstance: jest.fn(() => ({
      createRegistrationLink: (...args: unknown[]) => mockCreateRegistrationLink(...args),
      createSharedCode: (...args: unknown[]) => mockCreateSharedCode(...args),
      exportRegistrations: (...args: unknown[]) => mockExportRegistrations(...args),
    })),
  },
}));

// saveAs uses URL.createObjectURL which jsdom does not implement — mock it out.
jest.mock("src/experiences/saveAs", () => ({
  saveAs: jest.fn(),
}));

const GIVEN_TOKEN = "admin-secret";

describe("AdminPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.location.hash = `#/admin-panel?token=${GIVEN_TOKEN}`;
  });

  afterEach(() => {
    window.location.hash = "";
  });

  test("shows the ErrorPage when no token is present in the URL", () => {
    window.location.hash = "#/admin-panel";
    render(<AdminPanel />);
    expect(screen.getByTestId(ERROR_PAGE_TEST_ID.ERROR_MESSAGE)).toBeInTheDocument();
    expect(screen.queryByTestId(DATA_TEST_ID.ADMIN_PANEL_CONTAINER)).not.toBeInTheDocument();
  });

  test("renders the six tool cards when a token is present", () => {
    render(<AdminPanel />);
    expect(screen.getByTestId(DATA_TEST_ID.ADMIN_PANEL_CONTAINER)).toBeInTheDocument();
    expect(screen.getByTestId(DATA_TEST_ID.CARD_GENERATE_LINK)).toBeInTheDocument();
    expect(screen.getByTestId(DATA_TEST_ID.CARD_SHARED_CODE)).toBeInTheDocument();
    expect(screen.getByTestId(DATA_TEST_ID.CARD_EXPORT)).toBeInTheDocument();
    expect(screen.getByTestId(DATA_TEST_ID.CARD_REPORTS)).toBeInTheDocument();
    expect(screen.getByTestId(DATA_TEST_ID.CARD_REPORT_LOOKUP)).toBeInTheDocument();
    expect(screen.getByTestId(DATA_TEST_ID.CARD_FAQ)).toBeInTheDocument();
  });

  test("opens the generate-link tool, submits a code, and shows a copy button (URL hidden)", async () => {
    const givenLink = "https://app.example.test/#/register?reg_code=0035cABC&report_token=sec";
    mockCreateRegistrationLink.mockResolvedValue({
      registration_code: "0035cABC",
      link: givenLink,
      already_used: false,
    });

    render(<AdminPanel />);
    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_GENERATE_LINK));
    expect(screen.getByTestId(LINK_TOOL_TEST_ID.GENERATE_LINK_TOOL)).toBeInTheDocument();

    fireEvent.change(screen.getByTestId(LINK_TOOL_TEST_ID.CODE_INPUT), { target: { value: "0035cABC" } });
    fireEvent.click(screen.getByTestId(LINK_TOOL_TEST_ID.SUBMIT_BUTTON));

    await waitFor(() => {
      expect(screen.getByTestId(LINK_TOOL_TEST_ID.LINK_READY)).toBeInTheDocument();
    });
    expect(mockCreateRegistrationLink).toHaveBeenCalledWith(GIVEN_TOKEN, "0035cABC");
    expect(screen.getByTestId(LINK_TOOL_TEST_ID.COPY_BUTTON)).toBeInTheDocument();
    // the raw URL is hidden by design — staff just copy & share it
    expect(screen.queryByTestId(LINK_TOOL_TEST_ID.RESULT_LINK)).not.toBeInTheDocument();
  });

  test("copies the generated link to the clipboard", async () => {
    const givenLink = "https://app.example.test/#/register?reg_code=0035cABC&report_token=sec";
    mockCreateRegistrationLink.mockResolvedValue({
      registration_code: "0035cABC",
      link: givenLink,
      already_used: false,
    });
    const mockWriteText = jest.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText: mockWriteText }, configurable: true });

    render(<AdminPanel />);
    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_GENERATE_LINK));
    fireEvent.change(screen.getByTestId(LINK_TOOL_TEST_ID.CODE_INPUT), { target: { value: "0035cABC" } });
    fireEvent.click(screen.getByTestId(LINK_TOOL_TEST_ID.SUBMIT_BUTTON));

    await waitFor(() => {
      expect(screen.getByTestId(LINK_TOOL_TEST_ID.COPY_BUTTON)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId(LINK_TOOL_TEST_ID.COPY_BUTTON));

    await waitFor(() => {
      expect(mockWriteText).toHaveBeenCalledWith(givenLink);
    });
  });

  test("warns when the registration code has already been used", async () => {
    mockCreateRegistrationLink.mockResolvedValue({
      registration_code: "0035cABC",
      link: "https://app.example.test/#/register?reg_code=0035cABC&report_token=sec",
      already_used: true,
    });

    render(<AdminPanel />);
    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_GENERATE_LINK));
    fireEvent.change(screen.getByTestId(LINK_TOOL_TEST_ID.CODE_INPUT), { target: { value: "0035cABC" } });
    fireEvent.click(screen.getByTestId(LINK_TOOL_TEST_ID.SUBMIT_BUTTON));

    await waitFor(() => {
      expect(screen.getByTestId(LINK_TOOL_TEST_ID.ALREADY_USED_WARNING)).toBeInTheDocument();
    });
  });

  test("shows an error when link generation fails", async () => {
    mockCreateRegistrationLink.mockRejectedValue(new Error("backend unavailable"));

    render(<AdminPanel />);
    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_GENERATE_LINK));
    fireEvent.change(screen.getByTestId(LINK_TOOL_TEST_ID.CODE_INPUT), { target: { value: "x" } });
    fireEvent.click(screen.getByTestId(LINK_TOOL_TEST_ID.SUBMIT_BUTTON));

    await waitFor(() => {
      expect(screen.getByTestId(LINK_TOOL_TEST_ID.ERROR)).toBeInTheDocument();
    });
  });

  test("creates a shared code", async () => {
    mockCreateSharedCode.mockResolvedValue({
      invitation_code: "grupo-2026",
      invitation_type: "REGISTER",
      allowed_usage: 999999,
      valid_from: "2026-01-01T00:00:00Z",
      valid_until: "2027-01-01T00:00:00Z",
      sensitive_personal_data_requirement: "NOT_AVAILABLE",
    });

    render(<AdminPanel />);
    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_SHARED_CODE));
    fireEvent.change(screen.getByTestId(SHARED_TOOL_TEST_ID.CODE_INPUT), { target: { value: "grupo-2026" } });
    fireEvent.click(screen.getByTestId(SHARED_TOOL_TEST_ID.SUBMIT_BUTTON));

    await waitFor(() => {
      expect(screen.getByTestId(SHARED_TOOL_TEST_ID.SUCCESS)).toBeInTheDocument();
    });
    expect(mockCreateSharedCode).toHaveBeenCalledWith(GIVEN_TOKEN, {
      invitation_code: "grupo-2026",
      invitation_type: "REGISTER",
    });
  });

  test("exports registrations", async () => {
    mockExportRegistrations.mockResolvedValue(new Blob(["user_id\n"], { type: "text/csv" }));

    render(<AdminPanel />);
    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_EXPORT));
    fireEvent.click(screen.getByTestId(EXPORT_TOOL_TEST_ID.EXPORT_BUTTON));

    await waitFor(() => {
      expect(screen.getByTestId(EXPORT_TOOL_TEST_ID.SUCCESS)).toBeInTheDocument();
    });
    expect(mockExportRegistrations).toHaveBeenCalledWith(GIVEN_TOKEN);
  });

  test("opens the report-lookup tool", () => {
    render(<AdminPanel />);
    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_REPORT_LOOKUP));
    expect(screen.getByTestId(REPORT_LOOKUP_TOOL_TEST_ID.REPORT_LOOKUP_TOOL)).toBeInTheDocument();
  });

  test("opens the general-FAQ tool and shows the report thumbnail", () => {
    render(<AdminPanel />);
    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_FAQ));
    expect(screen.getByTestId(GENERAL_FAQ_TOOL_TEST_ID.GENERAL_FAQ_TOOL)).toBeInTheDocument();
    expect(screen.getByTestId(GENERAL_FAQ_TOOL_TEST_ID.CV_THUMBNAIL)).toBeInTheDocument();
  });

  test("returns to the card grid via the back button", () => {
    render(<AdminPanel />);
    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_GENERATE_LINK));
    expect(screen.getByTestId(LINK_TOOL_TEST_ID.GENERATE_LINK_TOOL)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId(DATA_TEST_ID.BACK_BUTTON));
    expect(screen.getByTestId(DATA_TEST_ID.CARD_GENERATE_LINK)).toBeInTheDocument();
    expect(screen.queryByTestId(LINK_TOOL_TEST_ID.GENERATE_LINK_TOOL)).not.toBeInTheDocument();
  });
});
