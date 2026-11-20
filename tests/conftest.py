import logging
import subprocess
from collections.abc import Generator

import datajoint as dj
import pytest

logger = logging.getLogger(__name__)


def _docker_unavailable() -> str | None:
    """Return why Docker cannot run Linux containers here, or None when it can."""
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.OSType}}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        return "Docker is not installed"
    except subprocess.TimeoutExpired:
        return "Docker did not respond"
    if result.returncode != 0:
        return f"Docker is not running: {result.stderr.strip()}"
    # GitHub's Windows runners run Docker with Windows containers, which
    # cannot start the Linux MySQL image, so the database tests skip there.
    if result.stdout.strip() != "linux":
        return f"Docker runs {result.stdout.strip()} containers, not Linux"
    return None


DOCKER_UNAVAILABLE = _docker_unavailable()


@pytest.fixture
def file_store(tmp_path) -> Generator[str, None, None]:
    """Configure a local file store named "store" in a temporary directory."""
    old_stores = dict(dj.config.stores)
    dj.config.stores["store"] = {"protocol": "file", "location": str(tmp_path)}
    yield "store"
    dj.config.stores.clear()
    dj.config.stores.update(old_stores)


@pytest.fixture(scope="session")
def mysql_container():
    """Start a MySQL container for the test session."""
    if DOCKER_UNAVAILABLE:
        pytest.skip(DOCKER_UNAVAILABLE)
    from testcontainers.community.mysql import MySqlContainer

    container = MySqlContainer(
        image="mysql:8.0", username="root", password="password", dbname="test"
    )
    container.start()
    logger.info(
        "MySQL container started at %s:%s",
        container.get_container_host_ip(),
        container.get_exposed_port(3306),
    )
    yield container
    container.stop()


@pytest.fixture
def schema(mysql_container, file_store) -> Generator[dj.Schema, None, None]:
    """Connect to the MySQL container and create a test schema."""
    keys = ("database.host", "database.port", "database.user", "database.password")
    keys += ("database.use_tls", "safemode")
    old_config = {k: dj.config[k] for k in keys}

    host = mysql_container.get_container_host_ip()
    port = int(mysql_container.get_exposed_port(3306))
    dj.config["database.host"] = host
    dj.config["database.port"] = port
    dj.config["database.user"] = "root"
    dj.config["database.password"] = "password"
    dj.config["database.use_tls"] = False
    dj.config["safemode"] = False

    connection = dj.Connection(host=f"{host}:{port}", user="root", password="password")
    test_schema = dj.Schema("test_photon", connection=connection)
    yield test_schema
    test_schema.drop(prompt=False)
    connection.close()
    for k, v in old_config.items():
        dj.config[k] = v
