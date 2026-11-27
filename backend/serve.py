"""serve.py — container entry point: the API (QE_PORT, 8080) and the internal port (QE_INTERNAL_PORT,
9090) as two uvicorn servers in one process and one event loop.

Both share the in-memory data. Access logs are off (obs.TraceMiddleware writes one JSON line per
request); proxy headers are off (client IPs come from ratelimit with TRUST_PROXY). SIGTERM/SIGINT
set should_exit on both servers, so the API's lifespan shutdown runs to the end; running requests
get GRACEFUL_SECONDS to finish (the Helm grace period is longer: preStop pause + this + margin).
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys

import uvicorn

import obs

GRACEFUL_SECONDS = 20


class _Server(uvicorn.Server):
    """A server that leaves signal handling to main() (two servers cannot both own the signals)."""

    @contextlib.contextmanager
    def capture_signals(self):
        yield


def _port(name: str, default: int) -> int:
    return int(os.environ.get(name, "").strip() or default)


def build_servers() -> tuple[uvicorn.Config, uvicorn.Config]:
    common = {"host": os.environ.get("QE_HOST", "0.0.0.0"), "access_log": False,  # noqa: S104
              "proxy_headers": False, "server_header": False, "log_config": None,
              "timeout_graceful_shutdown": GRACEFUL_SECONDS}
    public = uvicorn.Config("app:app", port=_port("QE_PORT", 8080), lifespan="on", **common)
    private = uvicorn.Config("internal_app:app", port=_port("QE_INTERNAL_PORT", 9090),
                             lifespan="off", **common)
    return public, private


async def _serve() -> None:
    servers = [_Server(c) for c in build_servers()]
    loop = asyncio.get_running_loop()

    stopped_by_signal = False

    def _stop() -> None:
        for s in servers:
            s.should_exit = True

    def _on_signal() -> None:
        nonlocal stopped_by_signal
        stopped_by_signal = True
        _stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):   # Windows: no loop signal handlers
            loop.add_signal_handler(sig, _on_signal)
    tasks = [asyncio.create_task(s.serve()) for s in servers]
    # One server ending (signal, or a failed start such as a busy port) ends the other one too.
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    _stop()
    await asyncio.gather(*pending)
    for t in done:
        t.result()                                       # re-raise a failed start (exit code ≠ 0)
    if not stopped_by_signal and not servers[0].started:
        sys.exit(3)                                      # API lifespan startup failed (as uvicorn.run)


def main() -> None:
    obs.setup_logging()
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
