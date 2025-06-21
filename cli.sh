#!/bin/bash

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default command is --help if no arguments are provided
if [ $# -eq 0 ]; then
    set -- --help
fi

# Run the CLI command in the container
docker compose run --rm ai-assistant python -m app.cli "$@"
