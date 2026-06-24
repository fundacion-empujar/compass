// mute the console
import "src/_test_utilities/consoleMock";

import { render, screen, fireEvent } from "src/_test_utilities/test-utils";
import QuickReplyButtons, { DATA_TEST_ID } from "./QuickReplyButtons";

describe("QuickReplyButtons", () => {
  test("renders a button per option and fires onSelect with the clicked label", () => {
    // GIVEN two quick-reply options and an onSelect handler
    const onSelect = jest.fn();
    const options = [{ label: "Yes" }, { label: "No, that's all" }];

    // WHEN rendered
    render(<QuickReplyButtons options={options} onSelect={onSelect} />);

    // THEN one button is rendered per option, with its label
    const buttons = screen.getAllByTestId(DATA_TEST_ID.QUICK_REPLY_BUTTON);
    expect(buttons).toHaveLength(2);
    expect(screen.getByText("Yes")).toBeInTheDocument();
    expect(screen.getByText("No, that's all")).toBeInTheDocument();

    // AND clicking a button calls onSelect with that button's label
    fireEvent.click(buttons[1]);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("No, that's all");

    // AND no errors or warnings occurred
    expect(console.error).not.toHaveBeenCalled();
    expect(console.warn).not.toHaveBeenCalled();
  });

  test("shows the 'choose one' caption when there are 2+ options", () => {
    render(<QuickReplyButtons options={[{ label: "A" }, { label: "B" }]} onSelect={jest.fn()} />);
    expect(screen.getByTestId(DATA_TEST_ID.QUICK_REPLY_HEADER)).toBeInTheDocument();
  });

  test("hides the caption when there is a single option", () => {
    render(<QuickReplyButtons options={[{ label: "Only one" }]} onSelect={jest.fn()} />);
    expect(screen.queryByTestId(DATA_TEST_ID.QUICK_REPLY_HEADER)).not.toBeInTheDocument();
    expect(screen.getAllByTestId(DATA_TEST_ID.QUICK_REPLY_BUTTON)).toHaveLength(1);
  });

  test("renders nothing when there are no options", () => {
    const { container } = render(<QuickReplyButtons options={[]} onSelect={jest.fn()} />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByTestId(DATA_TEST_ID.QUICK_REPLY_CONTAINER)).not.toBeInTheDocument();
  });
});
