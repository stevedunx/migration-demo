import argparse
import json
import logging
import os
import tempfile
from pathlib import Path

from .config import (
    DSM_CONTAINER,
    DTM_CONTAINER,
    NDSM_CONTAINER,
    STORAGE_ACCOUNT_URL,
    VERSION,
)
from .ndsm import calculate_ndsm
from .storage import (
    create_client,
    download_json,
    download_tif_gz_to_temp,
    download_tif_to_temp,
    upload_bytes,
)

logger = logging.getLogger(__name__)


def process_tile(
    tile_10k: str,
    tile_1k: str,
    client,
    dtm_index: dict,
) -> None:
    """Download the DSM and DTM for a 1k tile, compute the nDSM, and upload to blob storage."""
    dtm_tiles = {t["reference"]: t["file"] for t in dtm_index.get("tiles", [])}
    dtm_filename = dtm_tiles.get(tile_1k)
    if dtm_filename is None:
        raise ValueError(f"No DTM entry for tile {tile_1k} in DTM index")

    dsm_path = download_tif_to_temp(
        client, DSM_CONTAINER, f"{VERSION}/{tile_10k}/{tile_1k}.tif"
    )
    dtm_path = download_tif_gz_to_temp(
        client, DTM_CONTAINER, f"{VERSION}/{tile_10k}/{dtm_filename}"
    )

    try:
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            ndsm_tmp = Path(tmp.name)
        try:
            calculate_ndsm(dsm_path, dtm_path, ndsm_tmp)

            ndsm_tif_blob = f"{VERSION}/{tile_10k}/{tile_1k}.tif"
            upload_bytes(client, NDSM_CONTAINER, ndsm_tif_blob, ndsm_tmp.read_bytes())

            metadata = download_json(
                client, DSM_CONTAINER, f"{VERSION}/{tile_10k}/{tile_1k}.json"
            )
            ndsm_json_blob = f"{VERSION}/{tile_10k}/{tile_1k}.json"
            upload_bytes(
                client,
                NDSM_CONTAINER,
                ndsm_json_blob,
                json.dumps(metadata, indent=2).encode(),
            )

            logger.info("Uploaded nDSM to %s/%s", NDSM_CONTAINER, ndsm_tif_blob)
        finally:
            ndsm_tmp.unlink(missing_ok=True)
    finally:
        dsm_path.unlink(missing_ok=True)
        dtm_path.unlink(missing_ok=True)


def run(
    tile_10k: str,
    connection_string: str | None = None,
) -> None:
    """Process all 1k tiles within a 10k BNG block and upload nDSM to blob storage."""
    if connection_string is None:
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

    client = create_client(
        connection_string=connection_string, account_url=STORAGE_ACCOUNT_URL
    )

    dtm_index = download_json(client, DTM_CONTAINER, f"{VERSION}/{tile_10k}/index.json")

    container_client = client.get_container_client(DSM_CONTAINER)
    blobs = container_client.list_blobs(name_starts_with=f"{VERSION}/{tile_10k}/")
    tiles_1k = sorted(Path(b.name).stem for b in blobs if b.name.endswith(".tif"))

    for tile_1k in tiles_1k:
        process_tile(tile_10k, tile_1k, client, dtm_index)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Calculate nDSM from DSM and DTM in Azure Blob Storage"
    )
    parser.add_argument("tile_10k", help="10k BNG tile reference (e.g. SP00)")
    args = parser.parse_args()
    run(args.tile_10k)


if __name__ == "__main__":
    main()
