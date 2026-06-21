import functools
import inspect
import json
import logging
import os
import sys
import time
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_STANDARD_RECORD_KEYS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message"
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_RECORD_KEYS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


logger = logging.getLogger("visionnaire")


def log_call(operation: str, context_keys: tuple[str, ...] = ()) -> Callable[[F], F]:
    """Logs duration + outcome for an async service call as a JSON line.

    Only the named ``context_keys`` are pulled from the call's arguments and
    logged — nothing is logged by default, so large payloads (image bytes,
    embedding vectors) are never accidentally written to logs.
    """

    def decorator(fn: F) -> F:
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind(*args, **kwargs)
            context = {
                k: bound.arguments[k] for k in context_keys if k in bound.arguments
            }
            start = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
                logger.info(
                    "%s completed",
                    operation,
                    extra={
                        "operation": operation,
                        "duration_ms": _elapsed_ms(start),
                        **context,
                    },
                )
                return result
            except Exception:
                logger.error(
                    "%s failed",
                    operation,
                    extra={
                        "operation": operation,
                        "duration_ms": _elapsed_ms(start),
                        **context,
                    },
                    exc_info=True,
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def _elapsed_ms(start: float) -> float:
    return round((time.monotonic() - start) * 1000, 1)
