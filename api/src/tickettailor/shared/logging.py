import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")

logger = logging.getLogger("tickettailor")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        correlation_id = correlation_id_ctx.get()
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key not in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                try:
                    json.dumps(val)
                    log_data[key] = val
                except (TypeError, OverflowError):
                    log_data[key] = str(val)
        return json.dumps(log_data)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        corr_id = request.headers.get("X-Correlation-Id") or request.headers.get(
            "X-Request-Id"
        )
        if not corr_id:
            corr_id = str(uuid.uuid4())

        token = correlation_id_ctx.set(corr_id)
        logger.info(f"Request started: {request.method} {request.url.path}")
        start_time = time.perf_counter()
        try:
            response: Response = await call_next(request)
            process_time = time.perf_counter() - start_time
            response.headers["X-Correlation-Id"] = corr_id
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"- Status: {response.status_code} - Latency: {process_time:.4f}s",
                extra={"status_code": response.status_code, "latency": process_time},
            )
            return response
        except Exception as e:
            process_time = time.perf_counter() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"- Exception: {str(e)}",
                exc_info=True,
                extra={"latency": process_time},
            )
            raise
        finally:
            correlation_id_ctx.reset(token)
