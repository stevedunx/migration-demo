import os

STORAGE_ACCOUNT_URL = os.getenv(
    "STORAGE_ACCOUNT_URL",
    "https://height-store-demo.blob.core.windows.net",
)

DSM_CONTAINER = "dsm"
DTM_CONTAINER = "dtm"
VERSION = "v1"

OUTPUT_DIR = os.getenv("NDSM_OUTPUT_DIR", "ndsm")
