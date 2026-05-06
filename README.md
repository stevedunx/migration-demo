# nDSM Creator

Calculates a normalised Digital Surface Model (nDSM) from a DSM and DTM held in Azure Blob Storage, using the formula **DSM − DTM = nDSM**. The output rasters are written to Azure Blob Storage.

[![CI](https://github.com/stevedunx/migration-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/stevedunx/migration-demo/actions/workflows/ci.yml)

## Background

Height data is commonly captured as a grid of elevation values, where each cell stores the height above sea level in metres for that location on the ground. Three related raster types are used here:

- **DSM (Digital Surface Model)** — records the elevation of the first return: the top of whatever is present at each point, including buildings, trees, and other above-ground features.
- **DTM (Digital Terrain Model)** — records the elevation of the bare ground surface, with above-ground objects removed, such as buildings and trees.
- **nDSM (normalised Digital Surface Model)** — the difference between the two. By subtracting the DTM from the DSM, the ground elevation is cancelled out, leaving the height of objects *above* the ground (e.g. a building 15 m tall will have an nDSM value of ~15 m regardless of where it sits in the landscape).

All rasters are projected in the British National Grid (EPSG:27700) and tiled using BNG references at two levels: 10 km × 10 km grid squares (e.g. `SP00`) subdivided into up to 100 1 km × 1 km tiles (e.g. `SP0000`). Each tile has approximately 1 m ground resolution (1000 × 1000 pixels).

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

The calculated nDSM is written to the same storage account in the `ndsm` container:

```
ndsm/
└── v1/
    └── <10k BNG Reference>/
        ├── <1k BNG Reference>.tif  nDSM elevation raster
        └── <1k BNG Reference>.json Tile metadata (copied from DSM source)
```

## Prerequisites

| Requirement | Version    | Notes                                              |
| ----------- | ---------- | -------------------------------------------------- |
| Python      | ≥ 3.13     |                                                    |
| Node.js     | LTS (≥ 20) | Required to install Azurite                        |
| Azurite     | 3.35.0     | Azure Blob Storage emulator used by the test suite |

### Install Node.js

Download and install the LTS release from [nodejs.org](https://nodejs.org/), or use a version manager:


```powershell
# Windows – using winget
winget install OpenJS.NodeJS.LTS
```

Verify the installation:

```bash
node --version
npm --version
```

### Install Azurite

Install Azurite once, globally:

```bash
npm install -g azurite@3.35.0
```

## Installation

### Install uv

[uv](https://docs.astral.sh/uv/) is the recommended way to manage the Python environment and dependencies.

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows – using winget
winget install --id=astral-sh.uv -e
```

Verify the installation:

```bash
uv --version
```

### Install the package

Create a virtual environment:

```bash
uv venv
```

Install the package and its runtime dependencies:

```bash
uv pip install -e .
```

Install with test dependencies:

```bash
uv pip install -e ".[test]"
```

> **Note:** If you are on a network that performs TLS inspection, add `--native-tls` to the install commands.

Activate the virtual environment before running any commands:

```bash
# macOS / Linux
source .venv/bin/activate
```

```powershell
# Windows
.venv\Scripts\activate
```

### Alternative: plain pip

If you prefer not to use uv, pip works too:

```bash
pip install -e .           # runtime only
pip install -e ".[test]"   # with test dependencies
```

Activate the environment before running commands:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

## Running

Process all 1 km tiles within a 10 km BNG block and upload the nDSM files to the `ndsm` container in blob storage:

```bash
ndsm-creator SP00
```

By default the application authenticates to Azure using `DefaultAzureCredential`. The following environment variables are supported:

| Variable                          | Default                                           | Description                                      |
| --------------------------------- | ------------------------------------------------- | ------------------------------------------------ |
| `STORAGE_ACCOUNT_URL`             | `https://height-store-demo.blob.core.example.net` | Azure Blob Storage account URL                   |
| `AZURE_STORAGE_CONNECTION_STRING` | _(unset)_                                         | If set, used instead of `DefaultAzureCredential` |

## Running the tests

Ensure the virtual environment is activated (see [Installation](#installation)), then:

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

