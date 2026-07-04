"""Project-specific exception types."""


class TraceWeaveError(Exception):
    """Base error for TraceWeave runtime failures."""


class ConfigError(TraceWeaveError):
    """Configuration is missing or invalid."""


class LLMAPIError(TraceWeaveError):
    """The configured LLM API failed."""


class LLMOutputParseError(TraceWeaveError):
    """The LLM response could not be parsed as JSON."""


class LLMOutputValidationError(TraceWeaveError):
    """The parsed LLM action failed protocol validation."""


class ToolNotFoundError(TraceWeaveError):
    """A requested tool is not registered."""


class ToolArgumentValidationError(TraceWeaveError):
    """A tool call failed JSON Schema validation."""


class ToolExecutionError(TraceWeaveError):
    """A tool handler failed while executing."""


class SessionStoreError(TraceWeaveError):
    """The SQLite session store failed."""


class MaxStepsExceededError(TraceWeaveError):
    """The agent loop exceeded its maximum step count."""

