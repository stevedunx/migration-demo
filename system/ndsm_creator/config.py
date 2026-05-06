import os

STORAGE_ACCOUNT_URL = os.getenv(
    "STORAGE_ACCOUNT_URL",
    "https://height-store-demo.blob.core.example.net",
)

DSM_CONTAINER = "dsm"
DTM_CONTAINER = "dtm"
NDSM_CONTAINER = "ndsm"
VERSION = "v1"
