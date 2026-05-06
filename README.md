# nDSM Creator

Calculates a normalised Digital Surface Model (nDSM) from a DSM and DTM held in Azure Blob Storage, using the formula **DSM − DTM = nDSM**. The output rasters are written locally.

## Data sources

### DSM (Digital Surface Model)

Storage account: `https://height-store-demo.blob.core.example.net/`

```
dsm/
└── v1/
    └── <10k BNG Reference>/        e.g. SP00
        ├── <1k BNG Reference>.tif  DSM elevation raster
        └── <1k BNG Reference>.json Tile metadata
```

### DTM (Digital Terrain Model)

Storage account: `https://height-store-demo.blob.core.example.net/`

```
dtm/
└── v1/
    └── <10k BNG Reference>/        e.g. SP00
        ├── index.json              Lists the files present in this folder
        └── <GUID>.tif.gz           Gzipped DTM elevation raster
```

The `index.json` file has the following structure, with up to 100 entries (one per 1 km tile in the 10 km block):

```json
{
  "tiles": [
    { "reference": "<1k BNG Reference>", "file": "<GUID>.tif.gz" },
    { "reference": "<1k BNG Reference>", "file": "<GUID>.tif.gz" }
  ]
}
```

### nDSM output

The calculated nDSM is written locally:

```
ndsm/
└── <10k BNG Reference>/
    ├── <1k BNG Reference>.tif  nDSM elevation raster
    └── <1k BNG Reference>.json Tile metadata (copied from DSM source)
```

## Prerequisites

| Requirement | Version | Notes                                              |
| ----------- | ------- | -------------------------------------------------- |
| Python      | ≥ 3.10  |                                                    |
| Azurite     | latest  | Azure Blob Storage emulator used by the test suite |

Install Azurite once, globally:

```bash
npm install -g azurite
```

## Installation

Install the package and its runtime dependencies:

```bash
pip install -e .
```

Install the package with test dependencies:

```bash
pip install -e ".[test]"
```

## Running

Process all 1 km tiles within a 10 km BNG block and write the nDSM files to the default `ndsm/` output directory:

```bash
ndsm-creator SP00
```

Write output to a custom directory:

```bash
ndsm-creator SP00 --output-dir /path/to/output
```

By default the application authenticates to Azure using `DefaultAzureCredential`. To override the storage account URL or output directory, set the following environment variables:

| Variable                          | Default                                           | Description                                      |
| --------------------------------- | ------------------------------------------------- | ------------------------------------------------ |
| `STORAGE_ACCOUNT_URL`             | `https://height-store-demo.blob.core.example.net` | Azure Blob Storage account URL                   |
| `NDSM_OUTPUT_DIR`                 | `ndsm`                                            | Local directory to write nDSM files into         |
| `AZURE_STORAGE_CONNECTION_STRING` | _(unset)_                                         | If set, used instead of `DefaultAzureCredential` |

## Running the tests

Ensure Azurite is installed (see [Prerequisites](#prerequisites)), then:

```bash
pytest
```

The test suite starts an Azurite blob service automatically on a free local port, uploads synthetic DSM and DTM tiles, and tears the service down when the session ends. No Azure account or credentials are required to run the tests.

### Test structure

| Module              | Scope       | Description                                                                |
| ------------------- | ----------- | -------------------------------------------------------------------------- |
| `TestCalculateNdsm` | Unit        | Tests the raster subtraction logic directly against local files            |
| `TestProcessTile`   | Integration | Tests downloading a single tile from Azurite and producing an nDSM         |
| `TestRun`           | End-to-end  | Tests the full `run()` flow against Azurite, covering discovery and output |

