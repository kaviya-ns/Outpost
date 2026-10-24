import os
import socket
import threading
import time

import pytest
import uvicorn
from httpx import ASGITransport, AsyncClient

from mocks import mock_platforms


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def mock_platform_url():
    port = _free_port()
    config = uvicorn.Config(mock_platforms.app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


@pytest.fixture
async def client(mock_platform_url, tmp_path):
    db_file = tmp_path / "outpost.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    os.environ["DISCOURSE_MOCK_URL"] = mock_platform_url
    os.environ["DEVTO_MOCK_URL"] = mock_platform_url
    os.environ["WEBHOOK_PARTNER_URL"] = mock_platform_url
    os.environ["LEMMY_BASE_URL"] = mock_platform_url
    os.environ["GHOST_URL"] = mock_platform_url
    os.environ["SIMULATION_MODE"] = "true"
    os.environ["S3_ENABLED"] = "false"
    os.environ["RECERT_SCHEDULER_ENABLED"] = "false"
    os.environ["MOCK_RULES_PAGE_URL"] = f"{mock_platform_url}/rules/community-guidelines.txt"

    from app.config import get_settings

    get_settings.cache_clear()

    from app.db import configure_engine, init_db, reset_db
    from app.main import app
    from app.seed import seed_destinations

    configure_engine(os.environ["DATABASE_URL"])
    await reset_db()
    await seed_destinations(force=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
