import gzip
import json
import tempfile
from pathlib import Path

from azure.storage.blob import BlobServiceClient


def create_client(
    connection_string: str | None = None,
    account_url: str | None = None,
) -> BlobServiceClient:
    """Create a BlobServiceClient from a connection string or account URL with DefaultAzureCredential."""
    if connection_string:
        return BlobServiceClient.from_connection_string(connection_string)
    if account_url:
        from azure.identity import DefaultAzureCredential

        return BlobServiceClient(
            account_url=account_url, credential=DefaultAzureCredential()
        )
    raise ValueError("Either connection_string or account_url must be provided")


def download_bytes(client: BlobServiceClient, container: str, blob_path: str) -> bytes:
    return (
        client.get_blob_client(container=container, blob=blob_path)
        .download_blob()
        .readall()
    )


def download_json(client: BlobServiceClient, container: str, blob_path: str) -> dict:
    return json.loads(download_bytes(client, container, blob_path))


def download_tif_to_temp(
    client: BlobServiceClient, container: str, blob_path: str
) -> Path:
    data = download_bytes(client, container, blob_path)
    tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    tmp.write(data)
    tmp.close()
    return Path(tmp.name)


def download_tif_gz_to_temp(
    client: BlobServiceClient, container: str, blob_path: str
) -> Path:
    data = download_bytes(client, container, blob_path)
    decompressed = gzip.decompress(data)
    tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    tmp.write(decompressed)
    tmp.close()
    return Path(tmp.name)
