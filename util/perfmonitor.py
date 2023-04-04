from functools import wraps
import logging
import time
from typing import Optional

from django.conf import settings


monitor_logger = logging.getLogger('perfmonitor')


def monitorperf(func):
    """Decorator to add performance checkpoints to a function.
    Output is printed to perfmonitor logger. Can be
    enabled/disabled with ENABLE_PERFORMANCE_MONITORING setting.

    Usage:
    @monitorperf
    def example():
        # do stuff
        example.checkpoint("description of 'stuff'")
        # do more stuff
        example.checkpoint("description of 'more stuff'")
    """
    def wrapper(*args, **kwargs):
        perfmonitor = PerfMonitor(func.__name__)
        perfmonitor.start()

        result = func(*args, **kwargs)

        perfmonitor.end()

        monitor_logger.info(str(perfmonitor))

        return result

    if settings.ENABLE_PERFORMANCE_MONITORING:
        return wraps(func)(wrapper)

    def dummy_checkpoint(*args, **kwargs):
        pass
    func.checkpoint = dummy_checkpoint
    return func

class PerfMonitor:
    def __init__(self, name: Optional[str] = None):
        self.checkpoints = []
        self.name = name
        self.previous = time.perf_counter()

    def start(self) -> None:
        self.previous = time.perf_counter()
        self.checkpoint(f"start {self.name}")

    def end(self) -> None:
        self.checkpoint(f"end {self.name}")

    def checkpoint(self, tag: str) -> None:
        self.checkpoints.append((tag, time.perf_counter() - self.previous))
        self.previous = time.perf_counter()

    def formatted(self, decimals: int = 2) -> str:
        lines = [f"{tag}: {time:.{decimals}f}" for tag, time in self.checkpoints]
        if len(self.checkpoints) > 1:
            lines.append(f"Total: {sum(t for _, t in self.checkpoints):.{decimals}f}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.formatted(5)
