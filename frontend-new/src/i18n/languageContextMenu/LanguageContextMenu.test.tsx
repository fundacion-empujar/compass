// mute chatty console
import "src/_test_utilities/consoleMock";

import { render, screen } from "src/_test_utilities/test-utils";
import React from "react";

import LanguageContextMenu, { DATA_TEST_ID } from "./LanguageContextMenu";
import ContextMenu from "src/theme/ContextMenu/ContextMenu";

jest.mock("src/i18n/languageContextMenu/parseEnvSupportedLocales", () => {
  const { Locale } = require("src/i18n/constants");
  return {
    parseEnvSupportedLocales: jest.fn().mockReturnValue([Locale.EN_GB, Locale.EN_US, Locale.ES_ES, Locale.ES_AR]),
  };
});

jest.mock("src/theme/ContextMenu/ContextMenu", () => {
  return {
    default: jest.fn().mockImplementation(({ children }) => <div data-testid="context-menu">{children}</div>),
    __esModule: true,
  };
});

describe("LanguageContextMenu", () => {
  it("should render the LanguageContextMenu with the default props", () => {
    // GIVEN some supported components.
    // AND the component is rendered
    render(<LanguageContextMenu />);

    // THEN the LanguageContextMenu should be rendered
    const actualLanguageContextMenu = screen.getByTestId(DATA_TEST_ID.AUTH_LANGUAGE_SELECTOR_BUTTON);
    expect(actualLanguageContextMenu).toBeInTheDocument();

    // AND the component should match the snapshot
    expect(actualLanguageContextMenu).toMatchSnapshot();

    // AND expect the ContextMenu to be rendered
    expect(ContextMenu).toHaveBeenCalled();

    // AND the calls should match the snapshot.
    expect((ContextMenu as jest.Mock).mock.calls).toMatchSnapshot();

    // AND no errors should be logged
    expect(console.error).not.toHaveBeenCalled();

    // AND no warnings should be logged
    expect(console.warn).not.toHaveBeenCalled();
  });
});
