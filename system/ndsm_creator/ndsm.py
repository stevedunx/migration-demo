from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject


def calculate_ndsm(dsm_path: Path, dtm_path: Path, output_path: Path) -> None:
    """Subtract DTM from DSM to produce an nDSM, reprojecting the DTM to match the DSM grid."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(dsm_path) as dsm_ds, rasterio.open(dtm_path) as dtm_ds:
        dsm_data = dsm_ds.read(1).astype(np.float32)
        nodata = dsm_ds.nodata

        profile = dsm_ds.profile.copy()
        profile.update(dtype=rasterio.float32)

        # Reproject DTM onto the DSM grid so both arrays are spatially aligned
        dtm_aligned = np.zeros(dsm_ds.shape, dtype=np.float32)
        reproject(
            source=rasterio.band(dtm_ds, 1),
            destination=dtm_aligned,
            src_transform=dtm_ds.transform,
            src_crs=dtm_ds.crs,
            dst_transform=dsm_ds.transform,
            dst_crs=dsm_ds.crs,
            resampling=Resampling.bilinear,
        )

        ndsm_data = dsm_data - dtm_aligned

        # Restore nodata where either source had nodata
        if nodata is not None:
            mask = (dsm_data == nodata) | (dtm_aligned == nodata)
            ndsm_data[mask] = nodata

        with rasterio.open(output_path, "w", **profile) as out_ds:
            out_ds.write(ndsm_data, 1)
