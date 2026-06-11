// mute chatty console
import "src/_test_utilities/consoleMock";

// standard sentry mock
import "src/_test_utilities/sentryMock";
import { render, screen } from "src/_test_utilities/test-utils";
import { AppErrorFallback } from "src/error/errorPage/AppErrorFallback";
import { DATA_TEST_ID } from "src/error/errorPage/ErrorPage";

// mock the bugReport component (rendered by ErrorPage)
jest.mock("src/feedback/bugReport/bugReportButton/BugReportButton", () => {
  const actual = jest.requireActual("src/feedback/bugReport/bugReportButton/BugReportButton");
  return {
    ...actual,
    __esModule: true,
    default: jest.fn().mockImplementation(() => {
      return <span data-testid={actual.DATA_TEST_ID.BUG_REPORT_BUTTON_CONTAINER}></span>;
    }),
  };
});

describe("AppErrorFallback", () => {
  test("shows the refresh button for a ChunkLoadError", () => {
    // GIVEN a ChunkLoadError
    const error = new Error("Loading chunk 3 failed.");
    error.name = "ChunkLoadError";

    // WHEN AppErrorFallback is rendered with it
    render(<AppErrorFallback error={error} />);

    // THEN the error page and the refresh button are shown
    expect(screen.getByTestId(DATA_TEST_ID.ERROR_CONTAINER)).toBeInTheDocument();
    expect(screen.getByTestId(DATA_TEST_ID.REFRESH_BUTTON)).toBeInTheDocument();
  });

  test("does not show the refresh button for a non-chunk error", () => {
    // GIVEN a generic (non-chunk) error
    // WHEN AppErrorFallback is rendered with it
    render(<AppErrorFallback error={new Error("boom")} />);

    // THEN the error page is shown without the refresh button
    expect(screen.getByTestId(DATA_TEST_ID.ERROR_CONTAINER)).toBeInTheDocument();
    expect(screen.queryByTestId(DATA_TEST_ID.REFRESH_BUTTON)).not.toBeInTheDocument();
  });
});
