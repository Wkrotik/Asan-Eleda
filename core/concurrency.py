"""Concurrency primitives for controlling resource usage.

This module provides centralized concurrency controls to prevent resource
exhaustion (GPU OOM, CPU memory pressure) when handling multiple requests.
"""

from __future__ import annotations

import asyncio
import os


# Semaphore to limit concurrent ML inference operations.
# This prevents memory exhaustion when multiple requests arrive simultaneously.
# The limit is configurable via environment variable; default of 2 is conservative
# for most hardware configurations (GPU or CPU).
_MAX_CONCURRENT_INFERENCE = int(os.environ.get("MAX_CONCURRENT_INFERENCE", "2"))

# The semaphore is created at module load time. This is safe because:
# 1. It's created in the main thread before any async code runs
# 2. asyncio.Semaphore doesn't require an event loop at creation time (Python 3.10+)
INFERENCE_SEMAPHORE: asyncio.Semaphore = asyncio.Semaphore(_MAX_CONCURRENT_INFERENCE)


def get_max_concurrent_inference() -> int:
    """Return the configured max concurrent inference limit."""
    return _MAX_CONCURRENT_INFERENCE
