import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from azure.storage.blob import BlobServiceClient

from ndsm_creator.main import process_tile, run
from ndsm_creator.ndsm import calculate_ndsm
from ndsm_creator.storage import create_client

from conftest import DTM_GUID, TILE_10K, TILE_1K

NDSM_CONTAINER = "ndsm"
VERSION = "v1"


# ---------------------------------------------------------------------------
# Unit tests – calculate_ndsm
# ---------------------------------------------------------------------------


class TestCalculateNdsm:
    def test_subtracts_dtm_from_dsm(self, tmp_path, dsm_raster, dtm_raster):
        output = tmp_path / "out" / "ndsm.tif"

        calculate_ndsm(dsm_raster, dtm_raster, output)

        assert output.exists()
        with rasterio.open(output) as ds:
            assert np.allclose(ds.read(1), 40.0)  # 50 - 10 = 40

    def test_creates_output_directory(self, tmp_path, dsm_raster, dtm_raster):
        output = tmp_path / "deep" / "nested" / "ndsm.tif"

        calculate_ndsm(dsm_raster, dtm_raster, output)

        assert output.exists()

    def test_output_crs_matches_dsm(self, tmp_path, dsm_raster, dtm_raster):
        output = tmp_path / "ndsm.tif"

        calculate_ndsm(dsm_raster, dtm_raster, output)

        with rasterio.open(dsm_raster) as dsm_ds, rasterio.open(output) as out_ds:
            assert out_ds.crs == dsm_ds.crs

    def test_output_transform_matches_dsm(self, tmp_path, dsm_raster, dtm_raster):
        output = tmp_path / "ndsm.tif"

        calculate_ndsm(dsm_raster, dtm_raster, output)

        with rasterio.open(dsm_raster) as dsm_ds, rasterio.open(output) as out_ds:
            assert out_ds.transform == dsm_ds.transform

    def test_preserves_nodata_pixels(
        self, tmp_path, dsm_raster_with_nodata, dtm_raster
    ):
        output = tmp_path / "ndsm.tif"

        calculate_ndsm(dsm_raster_with_nodata, dtm_raster, output)

        with rasterio.open(output) as ds:
            data = ds.read(1)
            assert data[0, 0] == ds.nodata, "nodata pixel should stay nodata"
            assert np.allclose(data[1:, :], 40.0), "valid pixels should be 50 - 10"

    def test_output_dtype_is_float32(self, tmp_path, dsm_raster, dtm_raster):
        output = tmp_path / "ndsm.tif"

        calculate_ndsm(dsm_raster, dtm_raster, output)

        with rasterio.open(output) as ds:
            assert ds.dtypes[0] == "float32"


# ---------------------------------------------------------------------------
# Integration tests – process_tile (uses Azurite)
# ---------------------------------------------------------------------------


class TestProcessTile:
    def _client(self, azurite):
        return create_client(connection_string=azurite)

    def _dtm_index(self):
        return {"tiles": [{"reference": TILE_1K, "file": f"{DTM_GUID}.tif.gz"}]}

    def _ndsm_blob(self, blob_client, tile_10k, tile_1k, ext):
        return blob_client.get_blob_client(
            NDSM_CONTAINER, f"{VERSION}/{tile_10k}/{tile_1k}.{ext}"
        )

    def test_produces_ndsm_tif_blob(self, azurite, blob_client, tile_data):
        tile_10k, tile_1k = tile_data

        process_tile(tile_10k, tile_1k, self._client(azurite), self._dtm_index())

        assert self._ndsm_blob(blob_client, tile_10k, tile_1k, "tif").exists()

    def test_ndsm_tif_values_are_correct(self, azurite, blob_client, tile_data):
        tile_10k, tile_1k = tile_data

        process_tile(tile_10k, tile_1k, self._client(azurite), self._dtm_index())

        data = (
            self._ndsm_blob(blob_client, tile_10k, tile_1k, "tif")
            .download_blob()
            .readall()
        )
        with MemoryFile(data) as mem:
            with mem.open() as ds:
                assert np.allclose(ds.read(1), 40.0)

    def test_produces_metadata_json_blob(self, azurite, blob_client, tile_data):
        tile_10k, tile_1k = tile_data

        process_tile(tile_10k, tile_1k, self._client(azurite), self._dtm_index())

        raw = (
            self._ndsm_blob(blob_client, tile_10k, tile_1k, "json")
            .download_blob()
            .readall()
        )
        metadata = json.loads(raw)
        assert metadata["tile"] == tile_1k

    def test_raises_for_missing_dtm_index_entry(self, azurite, tile_data):
        tile_10k, tile_1k = tile_data
        empty_index = {"tiles": []}

        with pytest.raises(ValueError, match="No DTM entry"):
            process_tile(tile_10k, tile_1k, self._client(azurite), empty_index)


# ---------------------------------------------------------------------------
# End-to-end tests – run (uses Azurite)
# ---------------------------------------------------------------------------


class TestRun:
    def _ndsm_blob(self, blob_client, tile_10k, tile_1k, ext):
        return blob_client.get_blob_client(
            NDSM_CONTAINER, f"{VERSION}/{tile_10k}/{tile_1k}.{ext}"
        )

    def test_produces_ndsm_blobs(self, azurite, blob_client, tile_data):
        tile_10k, tile_1k = tile_data

        run(tile_10k, connection_string=azurite)

        assert self._ndsm_blob(blob_client, tile_10k, tile_1k, "tif").exists()
        assert self._ndsm_blob(blob_client, tile_10k, tile_1k, "json").exists()

    def test_ndsm_values_are_correct(self, azurite, blob_client, tile_data):
        tile_10k, tile_1k = tile_data

        run(tile_10k, connection_string=azurite)

        data = (
            self._ndsm_blob(blob_client, tile_10k, tile_1k, "tif")
            .download_blob()
            .readall()
        )
        with MemoryFile(data) as mem:
            with mem.open() as ds:
                assert np.allclose(ds.read(1), 40.0)
