# Sketch Engine API Client

This is an auto-generated Python client for the [Sketch Engine API](https://api.sketchengine.eu/). It provides a convenient way to interact with Sketch Engine's corpus linguistics services programmatically.

## Overview

The client is automatically generated from the OpenAPI specification (`openapi.yaml`) using the `client_generator.py` script. It provides a Python class `SketchEngineClient` with methods for all available Sketch Engine API endpoints, handling authentication and request formatting.

## Structure

- `client.py` - The main auto-generated client containing the `SketchEngineClient` class
- `client_generator.py` - Script that generates the client from the OpenAPI spec
- `openapi.yaml` - OpenAPI specification defining the Sketch Engine API endpoints

## Usage

```python
from client import SketchEngineClient

# Initialize the client with your API key
client = SketchEngineClient(api_key="your_api_key")

# Example: Get corpus information
response = client.get_search_corp_info(
    corpname="preloaded/bnc2",  # Corpus name
    format="json"               # Response format
)

# Example: Search concordance
response = client.get_search_concordance(
    corpname="preloaded/bnc2",
    q="lemma",                 # Query
    pagesize=20                # Results per page
)
```

## Authentication

The client uses bearer token authentication. You need to obtain an API key from Sketch Engine and provide it when initializing the `SketchEngineClient`. The client automatically handles adding the authentication token to all requests.

## Available Methods

The `SketchEngineClient` class provides methods for various Sketch Engine operations including:

- Corpus information and statistics (`get_search_corp_info`)
- Word lists and frequency analysis (`get_search_wordlist`, `get_search_freqml`)
- Concordance searches (`get_search_concordance`)
- Thesaurus lookups (`get_search_thes`)
- Word sketches (`get_search_wsketch`)
- Word sketch differences (`get_search_wsdiff`)
- Corpus compilation and management (various `ca/api/corpora` endpoints)
- Document management
- And more...

Each method is documented with its parameters and their descriptions in the docstrings.

## Requirements

- Python 3.6+
- `requests` library

## Generation

To regenerate the client from an updated OpenAPI specification:

```bash
python client_generator.py openapi.yaml [output_file.py]
```

This will read the `openapi.yaml` file and generate an updated `client.py`. If no output file is specified, it defaults to `generated_sketchengine_client.py`. 