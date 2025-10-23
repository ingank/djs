import logging
from logging import Handler, StreamHandler, FileHandler
from typing import Optional

TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")

def trace(self, message: str, *args, **kwargs) -> None:
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, message, args, **kwargs)

logging.Logger.trace = trace  # type: ignore

class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

def _map_level(verbose: int, quiet: int) -> int:
    if verbose >= 3:
        return TRACE_LEVEL
    if verbose == 2:
        return logging.DEBUG
    if verbose == 1:
        return logging.INFO
    if quiet >= 2:
        return logging.CRITICAL
    if quiet == 1:
        return logging.ERROR
    return logging.WARNING

def _make_handler(stream: bool, filename: Optional[str] = None) -> Handler:
    handler: Handler = StreamHandler() if stream else FileHandler(filename)  # type: ignore[arg-type]
    handler.setFormatter(TextFormatter())
    return handler

def setup_logging(*, verbose: int = 0, quiet: int = 0, log_file: Optional[str] = None) -> logging.Logger:
    level = _map_level(verbose, quiet)
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(_make_handler(stream=True))
    if log_file:
        root.addHandler(_make_handler(stream=False, filename=log_file))
    return logging.getLogger("djs")
