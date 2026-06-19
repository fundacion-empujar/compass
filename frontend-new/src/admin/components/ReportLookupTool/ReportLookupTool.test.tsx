// silence chatty console
import "src/_test_utilities/consoleMock";

import React from "react";
import { render, screen, fireEvent } from "src/_test_utilities/test-utils";
import ReportLookupTool, { DATA_TEST_ID } from "src/admin/components/ReportLookupTool/ReportLookupTool";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => mockNavigate,
}));

const GIVEN_TOKEN = "admin-secret";

describe("ReportLookupTool", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("navigates to the individual report, forwarding the admin token", () => {
    render(<ReportLookupTool token={GIVEN_TOKEN} />);

    fireEvent.change(screen.getByTestId(DATA_TEST_ID.CODE_INPUT), { target: { value: "0035cABC" } });
    fireEvent.click(screen.getByTestId(DATA_TEST_ID.SUBMIT_BUTTON));

    expect(mockNavigate).toHaveBeenCalledWith(`/report/0035cABC?token=${GIVEN_TOKEN}`);
  });

  test("disables the button and does not navigate when the input is empty", () => {
    render(<ReportLookupTool token={GIVEN_TOKEN} />);

    expect(screen.getByTestId(DATA_TEST_ID.SUBMIT_BUTTON)).toBeDisabled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
