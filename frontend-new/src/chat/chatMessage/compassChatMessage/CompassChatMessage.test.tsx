// mute the console
import "src/_test_utilities/consoleMock";

import CompassChatMessage, { COMPASS_CHAT_MESSAGE_TYPE, DATA_TEST_ID } from "./CompassChatMessage";
import ChatMessageFooterLayout, {
  DATA_TEST_ID as CHAT_MESSAGE_FOOTER_DATA_TEST_ID,
} from "src/chat/chatMessage/components/chatMessageFooter/ChatMessageFooterLayout";
import ChatBubble, {
  DATA_TEST_ID as CHAT_BUBBLE_DATA_TEST_ID,
} from "src/chat/chatMessage/components/chatBubble/ChatBubble";
import { render, screen, fireEvent } from "src/_test_utilities/test-utils";
import { ConversationMessageSender } from "src/chat/ChatService/ChatService.types";
import { nanoid } from "nanoid";
import Timestamp from "src/chat/chatMessage/components/chatMessageFooter/components/timestamp/Timestamp";
import { DATA_TEST_ID as QUICK_REPLY_DATA_TEST_ID } from "src/chat/chatMessage/suggestedActions/QuickReplyButtons";

jest.mock("src/chat/chatMessage/components/chatMessageFooter/ChatMessageFooterLayout", () => {
  const originalModule = jest.requireActual(
    "src/chat/chatMessage/components/chatMessageFooter/ChatMessageFooterLayout"
  );
  return {
    __esModule: true,
    ...originalModule,
    default: jest.fn(() => <div data-testid={originalModule.DATA_TEST_ID.CHAT_MESSAGE_FOOTER_LAYOUT_CONTAINER}></div>),
  };
});

jest.mock("src/chat/chatMessage/components/chatBubble/ChatBubble", () => {
  const originalModule = jest.requireActual("src/chat/chatMessage/components/chatBubble/ChatBubble");
  return {
    __esModule: true,
    ...originalModule,
    default: jest.fn(() => <div data-testid={originalModule.DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_CONTAINER}></div>),
  };
});

describe("render tests", () => {
  test("should render the Brújula Chat message with a timestamp", () => {
    // GIVEN a brujula chat message sent at a given time
    const givenDate = new Date(2024, 6, 25).toISOString();
    const messageData = {
      message_id: nanoid(),
      message: "Hello, I'm Brújula",
      sent_at: givenDate,
      type: COMPASS_CHAT_MESSAGE_TYPE,
      reaction: null,
    };
    // WHEN the user chat message is rendered
    render(<CompassChatMessage {...messageData} />);

    // THEN expect the message container to be visible
    expect(screen.getByTestId(DATA_TEST_ID.CHAT_MESSAGE_CONTAINER)).toBeInTheDocument();
    // AND expect the message bubble to be visible
    expect(screen.getByTestId(CHAT_BUBBLE_DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_CONTAINER)).toBeInTheDocument();
    // AND expect the message footer to be visible
    expect(
      screen.getByTestId(CHAT_MESSAGE_FOOTER_DATA_TEST_ID.CHAT_MESSAGE_FOOTER_LAYOUT_CONTAINER)
    ).toBeInTheDocument();

    // AND the correct date to have been displayed
    const footerLayoutCalls = (ChatMessageFooterLayout as jest.Mock).mock.calls.at(-1)[0];
    expect(footerLayoutCalls.children).toEqual(
      expect.objectContaining({
        type: Timestamp,
        props: {
          sentAt: givenDate,
        },
      })
    );
    // AND expect the Chat bubble to have been rendered with the expected message
    expect(ChatBubble).toHaveBeenNthCalledWith(
      1,
      {
        message: messageData.message,
        sender: ConversationMessageSender.COMPASS,
      },
      {}
    );

    // AND expect the component to match the snapshot
    expect(screen.getByTestId(DATA_TEST_ID.CHAT_MESSAGE_CONTAINER)).toMatchSnapshot();
    // THEN expect no errors or warnings to have occurred
    expect(console.error).not.toHaveBeenCalled();
    expect(console.warn).not.toHaveBeenCalled();
  });
});

describe("quick-reply options", () => {
  const baseMessage = {
    message_id: nanoid(),
    message: "Do you have more experiences?",
    sent_at: new Date(2024, 6, 25).toISOString(),
    reaction: null,
  };

  test("renders quick-reply buttons and forwards the clicked label", () => {
    // GIVEN a compass message with quick-reply options and a handler
    const onQuickReplyClick = jest.fn();

    // WHEN rendered
    render(
      <CompassChatMessage
        {...baseMessage}
        quick_reply_options={[{ label: "Yes" }, { label: "No" }]}
        onQuickReplyClick={onQuickReplyClick}
      />
    );

    // THEN the quick-reply buttons are visible
    const buttons = screen.getAllByTestId(QUICK_REPLY_DATA_TEST_ID.QUICK_REPLY_BUTTON);
    expect(buttons).toHaveLength(2);

    // AND clicking one forwards its label to the handler
    fireEvent.click(buttons[0]);
    expect(onQuickReplyClick).toHaveBeenCalledWith("Yes");

    // AND no errors or warnings occurred
    expect(console.error).not.toHaveBeenCalled();
    expect(console.warn).not.toHaveBeenCalled();
  });

  test("does not render quick-reply buttons when options are absent", () => {
    render(<CompassChatMessage {...baseMessage} />);
    expect(screen.queryByTestId(QUICK_REPLY_DATA_TEST_ID.QUICK_REPLY_CONTAINER)).not.toBeInTheDocument();

    // AND no errors or warnings occurred
    expect(console.error).not.toHaveBeenCalled();
    expect(console.warn).not.toHaveBeenCalled();
  });

  test("does not render quick-reply buttons when no handler is provided", () => {
    render(<CompassChatMessage {...baseMessage} quick_reply_options={[{ label: "Yes" }]} />);
    expect(screen.queryByTestId(QUICK_REPLY_DATA_TEST_ID.QUICK_REPLY_CONTAINER)).not.toBeInTheDocument();

    // AND no errors or warnings occurred
    expect(console.error).not.toHaveBeenCalled();
    expect(console.warn).not.toHaveBeenCalled();
  });
});
