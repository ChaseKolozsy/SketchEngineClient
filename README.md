# Sketch Engine API Client

This is an auto-generated Python client for the [Sketch Engine API](https://api.sketchengine.eu/). It provides a convenient way to interact with Sketch Engine's corpus linguistics services programmatically.

## Overview

The client is automatically generated from the OpenAPI specification (`openapi.yaml`) using the `client_generator.py` script. It provides Python functions for all available Sketch Engine API endpoints, handling authentication and request formatting.

## Structure

- `client.py` - The main auto-generated client containing all API endpoint functions
- `client_generator.py` - Script that generates the client from the OpenAPI spec
- `openapi.yaml` - OpenAPI specification defining the Sketch Engine API endpoints

## Usage

```python
from client import *

# All API calls require authentication via a bearer token
# Set your API key in the Authorization header of your requests

# Example: Get corpus information
response = get_search_corp_info(
    corpname="preloaded/bnc2",  # Corpus name
    format="json"               # Response format
)

# Example: Search concordance
response = get_search_concordance(
    corpname="preloaded/bnc2",
    q="lemma",                 # Query
    pagesize=20                # Results per page
)
```

## Available Functions

The client provides functions for various Sketch Engine operations including:

- Corpus information and statistics
- Word lists and frequency analysis
- Concordance searches
- Thesaurus lookups
- Word sketches
- Corpus compilation and management
- Document management
- And more...

Each function is documented with its parameters and their descriptions in the docstrings.

## Authentication

The API uses bearer token authentication. You need to obtain an API key from Sketch Engine and include it in the Authorization header of your requests.

## Requirements

- Python 3.6+
- `requests` library

## Generation

To regenerate the client from an updated OpenAPI specification:

```bash
python client_generator.py
```

This will read the `openapi.yaml` file and generate an updated `client.py`. 