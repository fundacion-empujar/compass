import type { Meta, StoryObj } from "@storybook/react";
import ChatBubble from "./ChatBubble";
import { ConversationMessageSender } from "src/chat/ChatService/ChatService.types";
import { VisualMock } from "src/_test_utilities/VisualMock";

const meta: Meta<typeof ChatBubble> = {
  title: "Chat/ChatBubble",
  component: ChatBubble,
  tags: ["autodocs"],
  argTypes: {},
};

export default meta;

type Story = StoryObj<typeof ChatBubble>;

export const FromCompass: Story = {
  args: {
    message: "Hello, how can I help you?",
    sender: ConversationMessageSender.COMPASS,
  },
};

export const FromUser: Story = {
  args: {
    message: "Hi there, I am a baker!",
    sender: ConversationMessageSender.USER,
  },
};

export const ShownWithFooter: Story = {
  args: {
    message: "Hello, how can I help you?",
    sender: ConversationMessageSender.COMPASS,
    children: <VisualMock text={"Foo Footer"} />,
  },
};

// --- Markdown rendering (COMPASS messages) ---
// Each story passes RAW markdown as `message`; ChatBubble renders it internally via ReactMarkdown.
// These cover the formatting the agent occasionally leaks despite its plain-text instructions.

export const Bold: Story = {
  args: {
    message: "You are a **Farm producer** with strong agricultural skills.",
    sender: ConversationMessageSender.COMPASS,
  },
};

export const ItalicAndBoldItalic: Story = {
  args: {
    message: "This is *important* and this is ***very important*** context.",
    sender: ConversationMessageSender.COMPASS,
  },
};

export const BulletList: Story = {
  args: {
    message:
      "Here is what I heard:\n\n- Social impact matters to you\n- You value a secure income\n- Growth opportunities are important",
    sender: ConversationMessageSender.COMPASS,
  },
};

export const InlineCode: Story = {
  args: {
    message: "Run `git status` and then `git commit` to save your work.",
    sender: ConversationMessageSender.COMPASS,
  },
};

// Reproduces the formatting bug: a fenced code block should wrap inside the bubble,
// never render as monospace, and never cause horizontal overflow.
export const FencedCodeBlock: Story = {
  args: {
    message:
      "Great! Here's a summary:\n\n```\nThis is a long single line inside a fenced code block that should wrap inside the bubble and never cause horizontal overflow of the chat bubble container at all costs.\n```\n\nThanks for sharing.",
    sender: ConversationMessageSender.COMPASS,
  },
};

export const WithLink: Story = {
  args: {
    message: "You can read more at [the Brújula site](https://brujula.example.org) when you are ready.",
    sender: ConversationMessageSender.COMPASS,
  },
};

// Validates remark-breaks: single "\n" line breaks and literal "•" bullets must be preserved,
// not collapsed into one paragraph (mirrors the collect-experiences recap message shape).
export const MultiLineRecap: Story = {
  args: {
    message:
      "Great! I've learned a lot about your preferences.\nHere's what matters to you:\n• Making a positive social impact\n• A secure job with reliable income\n• Good financial compensation\nThank you for sharing.",
    sender: ConversationMessageSender.COMPASS,
  },
};

// USER messages must NOT render markdown — raw asterisks/backticks stay literal.
export const UserWithMarkdownStaysLiteral: Story = {
  args: {
    message: "I have **experience** in farming and `tools`.",
    sender: ConversationMessageSender.USER,
  },
};
