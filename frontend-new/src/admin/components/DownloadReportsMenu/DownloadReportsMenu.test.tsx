// silence chatty console
import "src/_test_utilities/consoleMock";

import React from "react";
import { render, screen, fireEvent } from "src/_test_utilities/test-utils";
import DownloadReportsMenu, { DATA_TEST_ID } from "src/admin/components/DownloadReportsMenu/DownloadReportsMenu";
import { DATA_TEST_ID as REPORT_LOOKUP_TOOL_TEST_ID } from "src/admin/components/ReportLookupTool/ReportLookupTool";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => mockNavigate,
}));

const GIVEN_TOKEN = "admin-secret";

describe("DownloadReportsMenu", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("renders the two options (individual and bulk)", () => {
    render(<DownloadReportsMenu token={GIVEN_TOKEN} />);
    expect(screen.getByTestId(DATA_TEST_ID.DOWNLOAD_REPORTS_MENU)).toBeInTheDocument();
    expect(screen.getByTestId(DATA_TEST_ID.CARD_INDIVIDUAL)).toBeInTheDocument();
    expect(screen.getByTestId(DATA_TEST_ID.CARD_BULK)).toBeInTheDocument();
  });

  test("individual option shows the report-lookup form, and back returns to the options", () => {
    render(<DownloadReportsMenu token={GIVEN_TOKEN} />);

    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_INDIVIDUAL));
    expect(screen.getByTestId(REPORT_LOOKUP_TOOL_TEST_ID.REPORT_LOOKUP_TOOL)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId(DATA_TEST_ID.BACK_TO_OPTIONS));
    expect(screen.getByTestId(DATA_TEST_ID.CARD_INDIVIDUAL)).toBeInTheDocument();
    expect(screen.queryByTestId(REPORT_LOOKUP_TOOL_TEST_ID.REPORT_LOOKUP_TOOL)).not.toBeInTheDocument();
  });

  test("bulk option navigates to the bulk-download page, forwarding the admin token", () => {
    render(<DownloadReportsMenu token={GIVEN_TOKEN} />);

    fireEvent.click(screen.getByTestId(DATA_TEST_ID.CARD_BULK));
    expect(mockNavigate).toHaveBeenCalledWith(`/bulk-download-reports?token=${GIVEN_TOKEN}`);
  });
});
