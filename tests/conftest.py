"""Shared fixtures: one local server and one Edge instance for the whole test session."""

import pytest

from browser_support import free_port, sync_playwright
from hci import config
from hci.server import ServerThread, create_app


@pytest.fixture(scope="session")
def base_url():
    cfg = config.load()
    server = ServerThread(create_app(preview_site="g1-portal", cfg=cfg), "127.0.0.1", free_port()).start()
    yield server.url
    server.stop()


@pytest.fixture(scope="session")
def browser():
    if sync_playwright is None:
        pytest.skip("playwright is not installed")
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge", headless=True)
        except Exception as exc:            # no Edge on this machine
            pytest.skip(f"Microsoft Edge not available to Playwright: {exc}")
        yield b
        b.close()
