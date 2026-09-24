"""Logging setup with a per-request correlation ID.

Why contextvars: FastAPI handles requests concurrently; a ContextVar keeps the
request_id isolated per request without threading it through every call.
"""
from __future__ import annotations

import contextvars
import logging
import logging.config
from pathlib import Path

import yaml

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

DEFAULT_FORMAT = "%(asctime)s %(levelname)-5s %(name)s [request_id=%(request_id)s] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging(level: str = "INFO", log_file: str | None = None, config_file: str | None = None) -> None:
    """Initialise logging from logging.yaml when available, else a sane default.

    The configured log file always wins over the path in logging.yaml so there is
    exactly one place (config.yaml / env) to change paths.
    """
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    if config_file and Path(config_file).is_file():
        with open(config_file, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        if log_file and "file" in cfg.get("handlers", {}):
            cfg["handlers"]["file"]["filename"] = log_file
        elif "file" in cfg.get("handlers", {}):
            cfg["handlers"].pop("file")
            cfg["root"]["handlers"] = [h for h in cfg["root"]["handlers"] if h != "file"]
        cfg.setdefault("root", {})["level"] = level.upper()
        logging.config.dictConfig(cfg)
        return

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    formatter = logging.Formatter(DEFAULT_FORMAT, DATE_FORMAT)
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in handlers:
        h.setFormatter(formatter)
        h.addFilter(RequestIdFilter())
        root.addHandler(h)
    root.setLevel(level.upper())


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(component)
