// mute the console
import "src/_test_utilities/consoleMock";

// NOTE: react-markdown + remark-gfm/remark-breaks are globally mocked in src/setupTests.ts (the lightweight
// renderer mirrors inline bold/italic/code), so these tests can assert on the produced markdown elements
// without loading the real ESM dependency tree. Real rendering is verified in Storybook.

import ChatBubble, { DATA_TEST_ID } from "src/chat/chatMessage/components/chatBubble/ChatBubble";
import { render, screen } from "src/_test_utilities/test-utils";
import { ConversationMessageSender } from "src/chat/ChatService/ChatService.types";

describe("render tests", () => {
  test("should render the Chat Bubble without a child if none is passed", () => {
    // GIVEN a message
    const givenMessage: string = "Hello, I'm Brújula";
    // AND a sender
    const givenSender: ConversationMessageSender = ConversationMessageSender.COMPASS;

    // WHEN the chat bubble is rendered
    render(<ChatBubble message={givenMessage} sender={givenSender} />);

    // THEN expect the message container to be visible
    expect(screen.getByTestId(DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_CONTAINER)).toBeInTheDocument();
    // AND expect the message text to be visible
    expect(screen.getByTestId(DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_MESSAGE_TEXT)).toBeInTheDocument();

    // AND expect the component to match the snapshot
    expect(screen.getByTestId(DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_CONTAINER)).toMatchSnapshot();
  });

  test("should render the Chat Bubble with a child if one is passed", () => {
    // GIVEN a message
    const givenMessage: string = "Hello, I'm Brújula";
    // AND a sender
    const givenSender: ConversationMessageSender = ConversationMessageSender.COMPASS;
    // AND a footer
    const givenFooter = <div data-testid={"foo-footer"}>foo child</div>;

    // WHEN the chat bubble is rendered
    render(
      <ChatBubble message={givenMessage} sender={givenSender}>
        {givenFooter}
      </ChatBubble>
    );

    // THEN expect the message container to be visible
    expect(screen.getByTestId(DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_CONTAINER)).toBeInTheDocument();
    // AND expect the message text to be visible
    expect(screen.getByTestId(DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_MESSAGE_TEXT)).toBeInTheDocument();
    // AND expect the child container to be visible
    expect(screen.getByTestId(DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_MESSAGE_FOOTER_CONTAINER)).toBeInTheDocument();
    // AND expect the child to be visible
    expect(screen.getByTestId(givenFooter.props["data-testid"])).toBeInTheDocument();

    // AND expect the component to match the snapshot
    expect(screen.getByTestId(DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_CONTAINER)).toMatchSnapshot();
  });

  test("should render bold markdown as <strong> in COMPASS messages", () => {
    // GIVEN a COMPASS message containing bold markdown
    const givenMessage: string = "You are a **Farm producer** with great skills.";

    // WHEN the chat bubble is rendered
    render(<ChatBubble message={givenMessage} sender={ConversationMessageSender.COMPASS} />);

    // THEN expect the bold text to render as a <strong> element
    expect(screen.getByText("Farm producer").tagName).toBe("STRONG");
    // AND expect the raw asterisks not to appear in the document
    expect(screen.queryByText(/\*\*Farm producer\*\*/)).not.toBeInTheDocument();
  });

  test("should render inline code markdown as <code> in COMPASS messages", () => {
    // GIVEN a COMPASS message containing inline code (backticks)
    const givenMessage: string = "Use `git status` to check your changes.";

    // WHEN the chat bubble is rendered
    render(<ChatBubble message={givenMessage} sender={ConversationMessageSender.COMPASS} />);

    // THEN expect the code text to render as a <code> element
    expect(screen.getByText("git status").tagName).toBe("CODE");
    // AND expect the raw backticks not to appear in the document
    expect(screen.queryByText(/`git status`/)).not.toBeInTheDocument();
  });

  test("should render italic markdown as <em> in COMPASS messages", () => {
    // GIVEN a COMPASS message containing italic markdown
    const givenMessage: string = "This is *important* context.";

    // WHEN the chat bubble is rendered
    render(<ChatBubble message={givenMessage} sender={ConversationMessageSender.COMPASS} />);

    // THEN expect the italic text to render as an <em> element
    expect(screen.getByText("important").tagName).toBe("EM");
  });

  test("should NOT render markdown in USER messages", () => {
    // GIVEN a USER message containing bold markdown
    const givenMessage: string = "I have **experience** in farming.";

    // WHEN the chat bubble is rendered
    render(<ChatBubble message={givenMessage} sender={ConversationMessageSender.USER} />);

    // THEN expect the raw markdown to be preserved verbatim (no <strong> split)
    expect(screen.getByTestId(DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_MESSAGE_TEXT)).toHaveTextContent(
      "I have **experience** in farming."
    );
    expect(screen.queryByText("experience")).not.toBeInTheDocument();
  });
});
