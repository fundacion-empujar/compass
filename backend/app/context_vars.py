import contextvars

# Define a context variable to store the session_id, which will be used to correlate log messages
# every conversation with a user will have a unique session_id
session_id_ctx_var = contextvars.ContextVar("session_id", default=":none:")

# Define a context variable to store the user_id, which will be used to correlate log messages
# every user will have a unique user_id
user_id_ctx_var = contextvars.ContextVar("user_id", default=":none:")

# Client ID is a unique identifier for the device or client (browser) using our application.
# Client ID is optional, so we set a default value of None
client_id_ctx_var = contextvars.ContextVar("client_id", default=None)

# The language the user is speaking.
user_language_ctx_var = contextvars.ContextVar("user_language")

# Active agent_type within the current iteration of the AgentDirector loop;
# used for observability logging during agent execution.
agent_type_ctx_var = contextvars.ContextVar("agent_type", default=":none:")

# Current conversation phase; updated when the AgentDirector transitions phases.
# Typed as str | int because ConversationPhase is an int-valued Enum, so .set()
# receives either the enum's int value during transitions or the ":none:" sentinel.
phase_ctx_var: contextvars.ContextVar[str | int] = contextvars.ContextVar("phase", default=":none:")
