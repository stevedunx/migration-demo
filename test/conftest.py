"""
Pytest configuration and fixtures for nDSM Creator tests.

Prerequisites:
  - Azurite must be installed: npm install -g azurite
  - The `azurite-blob` command must be available on PATH.
"""

import gzip
import json
import socket
import subprocess
import time
from pathlib import Path

import numpy as np
import pytest
import rasterio
from azure.storage.blob import BlobServiceClient
from rasterio.crs import CRS
from rasterio.transform import from_bounds

# ---------------------------------------------------------------------------
# Well-known Azurite development credentials (public, not secret)
# ---------------------------------------------------------------------------
_AZURITE_ACCOUNT = "devstoreaccount1"
_AZURITE_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tiqw1234567890=="
)

TILE_10K = "SP00"
TILE_1K = "SP0000"
DTM_GUID = "550e8400-e29b-41d4-a716-446655440000"


# ---------------------------------------------------------------------------
# Azurite lifecycle
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


@pytest.fixture(scope="session")
def azurite(tmp_path_factory):  # yields str
    """Start an Azurite blob-only service and yield its connection string."""
    port = _free_port()
    workspace = tmp_path_factory.mktemp("azurite_data")

    proc = subprocess.Popen(
        [
            "azurite-blob",
            "--blobPort",
            str(port),
            "--blobHost",
            "127.0.0.1",
            "--location",
            str(workspace),
            "--silent",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not _wait_for_port("127.0.0.1", port):
        proc.terminate()
        pytest.fail(
            "Azurite blob service did not start. "
            "Install it with: npm install -g azurite"
        )

    conn_str = (
        f"DefaultEndpointsProtocol=http;"
        f"AccountName={_AZURITE_ACCOUNT};"
        f"AccountKey={_AZURITE_KEY};"
        f"BlobEndpoint=http://127.0.0.1:{port}/{_AZURITE_ACCOUNT};"
    )
    yield conn_str

    proc.terminate()
    proc.wait()


# ---------------------------------------------------------------------------
# Shared storage client with pre-created containers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def blob_client(azurite) -> BlobServiceClient:
    """Return a BlobServiceClient connected to Azurite with containers created."""
    client = BlobServiceClient.from_connection_string(azurite)
    client.create_container("dsm")
    client.create_container("dtm")
    return client


# ---------------------------------------------------------------------------
# Raster helpers
# ---------------------------------------------------------------------------

# BNG coordinates for a 1 km tile (SP0000 corner)
_TRANSFORM = from_bounds(440000, 250000, 441000, 251000, 10, 10)
_CRS = CRS.from_epsg(27700)
_NODATA = -9999.0


def _make_tif(data: np.ndarray) -> bytes:
    """Return in-memory GeoTIFF bytes for *data* on a fixed 10x10 BNG grid."""
    with rasterio.MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            count=1,
            dtype=data.dtype,
            crs=_CRS,
            transform=_TRANSFORM,
            nodata=_NODATA,
        ) as ds:
            ds.write(data, 1)
        return mem.read()


def make_tif_file(data: np.ndarray, path: Path) -> Path:
    """Write a GeoTIFF to *path* and return the path."""
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs=_CRS,
        transform=_TRANSFORM,
        nodata=_NODATA,
    ) as ds:
        ds.write(data, 1)
    return path


# ---------------------------------------------------------------------------
# Local raster fixtures (unit tests)
# ---------------------------------------------------------------------------


@pytest.fixture()
def dsm_raster(tmp_path) -> Path:
    data = np.full((10, 10), 50.0, dtype=np.float32)
    return make_tif_file(data, tmp_path / "dsm.tif")


@pytest.fixture()
def dtm_raster(tmp_path) -> Path:
    data = np.full((10, 10), 10.0, dtype=np.float32)
    return make_tif_file(data, tmp_path / "dtm.tif")


@pytest.fixture()
def dsm_raster_with_nodata(tmp_path) -> Path:
    data = np.full((10, 10), 50.0, dtype=np.float32)
    data[0, 0] = _NODATA
    return make_tif_file(data, tmp_path / "dsm_nodata.tif")


# ---------------------------------------------------------------------------
# Azurite tile data (integration / end-to-end tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def tile_data(blob_client) -> tuple[str, str]:
    """
    Upload a minimal DSM + DTM tile set to Azurite and return (tile_10k, tile_1k).

    DTM index structure:
        { "tiles": { "<1k ref>": "<guid>.tif.gz" } }
    """
    dsm_data = np.full((10, 10), 50.0, dtype=np.float32)
    dtm_data = np.full((10, 10), 10.0, dtype=np.float32)

    dsm_bytes = _make_tif(dsm_data)
    dtm_gz_bytes = gzip.compress(_make_tif(dtm_data))
    metadata = json.dumps({"tile": TILE_1K, "version": "v1"}).encode()
    dtm_index = json.dumps({"tiles": {TILE_1K: f"{DTM_GUID}.tif.gz"}}).encode()

    def upload(container: str, path: str, data: bytes) -> None:
        blob_client.get_blob_client(container, path).upload_blob(data)

    upload("dsm", f"v1/{TILE_10K}/{TILE_1K}.tif", dsm_bytes)
    upload("dsm", f"v1/{TILE_10K}/{TILE_1K}.json", metadata)
    upload("dtm", f"v1/{TILE_10K}/index.json", dtm_index)
    upload("dtm", f"v1/{TILE_10K}/{DTM_GUID}.tif.gz", dtm_gz_bytes)

    return TILE_10K, TILE_1K
