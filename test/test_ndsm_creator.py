import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from azure.storage.blob import BlobServiceClient

from ndsm_creator.main import process_tile, run
from ndsm_creator.ndsm import calculate_ndsm
from ndsm_creator.storage import create_client

from conftest import DTM_GUID, TILE_10K, TILE_1K


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
        return {"tiles": {TILE_1K: f"{DTM_GUID}.tif.gz"}}

    def test_produces_ndsm_tif(self, tmp_path, azurite, tile_data):
        tile_10k, tile_1k = tile_data

        process_tile(
            tile_10k, tile_1k, self._client(azurite), self._dtm_index(), tmp_path
        )

        output_tif = tmp_path / tile_10k / f"{tile_1k}.tif"
        assert output_tif.exists()
        with rasterio.open(output_tif) as ds:
            assert np.allclose(ds.read(1), 40.0)

    def test_produces_metadata_json(self, tmp_path, azurite, tile_data):
        tile_10k, tile_1k = tile_data

        process_tile(
            tile_10k, tile_1k, self._client(azurite), self._dtm_index(), tmp_path
        )

        output_json = tmp_path / tile_10k / f"{tile_1k}.json"
        assert output_json.exists()
        metadata = json.loads(output_json.read_text())
        assert metadata["tile"] == tile_1k

    def test_raises_for_missing_dtm_index_entry(self, tmp_path, azurite, tile_data):
        tile_10k, tile_1k = tile_data
        empty_index = {"tiles": {}}

        with pytest.raises(ValueError, match="No DTM entry"):
            process_tile(
                tile_10k, tile_1k, self._client(azurite), empty_index, tmp_path
            )


# ---------------------------------------------------------------------------
# End-to-end tests – run (uses Azurite)
# ---------------------------------------------------------------------------


class TestRun:
    def test_processes_all_tiles_in_10k_block(self, tmp_path, azurite, tile_data):
        tile_10k, tile_1k = tile_data

        run(tile_10k, output_dir=tmp_path, connection_string=azurite)

        assert (tmp_path / tile_10k / f"{tile_1k}.tif").exists()
        assert (tmp_path / tile_10k / f"{tile_1k}.json").exists()

    def test_ndsm_values_are_correct(self, tmp_path, azurite, tile_data):
        tile_10k, tile_1k = tile_data

        run(tile_10k, output_dir=tmp_path, connection_string=azurite)

        with rasterio.open(tmp_path / tile_10k / f"{tile_1k}.tif") as ds:
            assert np.allclose(ds.read(1), 40.0)
