import React from "react";
import { ConversationMessageSender } from "src/chat/ChatService/ChatService.types";
import { Box, Typography, styled, alpha } from "@mui/material";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";

export interface ChatBubbleProps {
  message: string | React.ReactNode;
  sender: ConversationMessageSender;
  children?: React.ReactNode;
}

const uniqueId = "6e685eeb-2b54-432a-8b66-8a81633b3981";

export const DATA_TEST_ID = {
  CHAT_MESSAGE_BUBBLE_CONTAINER: `chat-message-bubble-container-${uniqueId}`,
  CHAT_MESSAGE_BUBBLE_MESSAGE_TEXT: `chat-message-bubble-message-text-${uniqueId}`,
  CHAT_MESSAGE_BUBBLE_MESSAGE_FOOTER_CONTAINER: `chat-message-bubble-message-footer-container-${uniqueId}`,
};

const MessageBubble = styled(Box)<{ origin: ConversationMessageSender }>(({ theme, origin }) => ({
  width: "fit-content",
  variants: "outlined",
  wordWrap: "break-word",
  wordBreak: "break-word",
  padding: theme.fixedSpacing(theme.tabiyaSpacing.sm),
  border: origin === ConversationMessageSender.USER ? `2px solid ${theme.palette.primary.light}` : "none",
  borderRadius: origin === ConversationMessageSender.USER ? "12px 0px 12px 12px" : "12px 12px 12px 0px",
  backgroundColor:
    origin === ConversationMessageSender.USER ? alpha(theme.palette.primary.light, 0.16) : theme.palette.grey[100],
  color: origin === ConversationMessageSender.USER ? theme.palette.primary.contrastText : theme.palette.text.primary,
  position: "relative",
  alignSelf: origin === ConversationMessageSender.USER ? "flex-end" : "flex-start",
  display: "flex",
  flexDirection: "column",
  // Markdown element styles — only apply to COMPASS messages rendered via ReactMarkdown.
  // Goal: keep leaked agent markdown looking like plain chat text (no monospace, no overflow).
  "& p": { margin: 0 },
  "& p + p": { marginTop: theme.fixedSpacing(theme.tabiyaSpacing.xs) },
  "& strong": { fontWeight: 700 },
  "& em": { fontStyle: "italic" },
  "& ul, & ol": { paddingLeft: theme.fixedSpacing(theme.tabiyaSpacing.md), margin: 0 },
  "& li": { marginBottom: theme.fixedSpacing(theme.tabiyaSpacing.xxs) },
  "& a": { color: theme.palette.primary.main, textDecoration: "underline" },
  "& code": { fontFamily: "inherit", whiteSpace: "pre-wrap", wordBreak: "break-word" },
  // fontFamily must be set on pre itself — code inside pre would otherwise inherit monospace from pre.
  "& pre": {
    fontFamily: "inherit",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    overflowWrap: "break-word",
    margin: 0,
    maxWidth: "100%",
  },
}));

const ChatBubble: React.FC<ChatBubbleProps> = ({ message, sender, children }) => {
  // Render markdown only for AI (COMPASS) string messages; everything else stays plain text.
  const isCompassMarkdown = sender === ConversationMessageSender.COMPASS && typeof message === "string";

  return (
    <MessageBubble origin={sender} data-testid={DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_CONTAINER}>
      {isCompassMarkdown ? (
        <Box data-testid={DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_MESSAGE_TEXT}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkBreaks]}
            components={{
              // Open links safely in a new tab. No rehype-raw, so embedded HTML stays escaped.
              a: ({ node, children, ...props }) => (
                <a {...props} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
            }}
          >
            {message as string}
          </ReactMarkdown>
        </Box>
      ) : (
        <Typography whiteSpace="pre-line" data-testid={DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_MESSAGE_TEXT}>
          {message}
        </Typography>
      )}
      <Box data-testid={DATA_TEST_ID.CHAT_MESSAGE_BUBBLE_MESSAGE_FOOTER_CONTAINER}>{children}</Box>
    </MessageBubble>
  );
};

export default ChatBubble;
