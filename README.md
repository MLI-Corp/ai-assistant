# OpenWebUI Integrated Invoicing Assistant

This project provides a backend assistant that integrates with OpenWebUI to monitor an email inbox for work authorizations, extracts relevant data, and then creates entries in InvoiceNinja (v5) and Google Calendar. It features a modular design and is intended to be run via Docker Compose.

## Core System Components

*   **Backend Assistant (`backend_assistant/`)**:
    *   Monitors a specified IMAP email inbox (e.g., Zoho, Gmail) for new messages.
    *   Parses emails to identify and extract work authorization details (Authorization ID, client info, service date/time, mileage).
    *   Integrates with a local **InvoiceNinja v5** instance (running on SQLite for lighter resource use) to create clients and invoices.
    *   Integrates with **Google Calendar** to create events for future services.
    *   Sends processing summaries and error notifications to a configurable **Webhook URL** (e.g., for Matrix/Beeper integration).
    *   Uses a local SQLite database for operational logs, geocoding cache, and client billing rates.
    *   Exposes a FastAPI for control, status, logs, and a WebSocket for real-time updates.
*   **InvoiceNinja (Docker Service)**: A local instance of InvoiceNinja v5, configured to use SQLite. Accessible at `http://localhost:9000`.
*   **OpenWebUI (Docker Service)**: A local instance of OpenWebUI. The backend assistant is designed to be integrated with it, providing status and control. Accessible at `http://localhost:3000`.
*   **(Optional) LLM Runner**: The `docker-compose.yml` can be configured to run a local LLM (e.g., Ollama) for OpenWebUI.

## Features

-   **Automated Email Processing**: Fetches and processes emails from an IMAP inbox.
-   **Data Extraction**: Identifies key information from authorization emails.
-   **Invoice Creation**: Automatically creates clients and invoices in InvoiceNinja.
-   **Calendar Scheduling**: Automatically creates events in Google Calendar for future-dated services.
-   **Webhook Notifications**: Sends detailed notifications about processing results.
-   **API & WebSocket**:
    -   REST API for controlling the assistant (start/stop monitoring), checking status, and retrieving logs.
    -   WebSocket for streaming real-time status updates to clients like OpenWebUI.
-   **Dockerized**: All components run in Docker containers for easy setup and deployment.
-   **Configurable**: Extensive configuration via environment variables.

## Prerequisites

-   Docker and Docker Compose
-   Python 3.11+ (for local development if not using Docker exclusively)
-   An email account with IMAP access.
-   Google Cloud Project with OAuth 2.0 credentials (Client ID, Client Secret) for Google Calendar integration (see `backend_assistant/README.md` for setup).

## Quick Start

1.  **Clone the Repository**
    ```bash
    git clone <repository-url>
    cd <repository-directory-name>
    ```

2.  **Set Up Environment Variables**
    *   **Main Docker Compose variables**: Copy `.env.template` to `.env` and customize if needed (e.g., `INVOICENINJA_APP_DEBUG`, `TZ`).
        ```bash
        cp .env.template .env
        ```
    *   **Backend Assistant variables**: Navigate to the `backend_assistant` directory, copy the template, and fill in your details.
        ```bash
        cd backend_assistant
        cp .env.assistant.template .env.assistant
        # Edit .env.assistant with your IMAP, InvoiceNinja, Google, Webhook details
        cd ..
        ```
        **Crucial**: Refer to `backend_assistant/README.md` for detailed instructions on setting up `IMAP_PASSWORD` (use App Passwords for 2FA accounts) and obtaining `GOOGLE_REFRESH_TOKEN`.

3.  **Client Billing Rates Configuration**
    *   Create or edit `backend_assistant/config/client_billing_rates.json`. A sample structure is in `backend_assistant/README.md`. This file is mounted into the assistant container.
    *   Example:
        ```bash
        mkdir -p backend_assistant/config
        echo "{ \"default\": { \"mileage_rate\": 0.50 } }" > backend_assistant/config/client_billing_rates.json
        ```

4.  **Build and Start Services**
    ```bash
    docker-compose up -d --build
    ```

5.  **Access Services**
    *   **InvoiceNinja UI**: `http://localhost:9000`
    *   **OpenWebUI**: `http://localhost:3000`
    *   **Backend Assistant API Docs**: `http://localhost:8001/docs`
    *   **Backend Assistant Health**: `http://localhost:8001/health`
    *   **Backend Assistant WebSocket**: `ws://localhost:8001/ws/status`

## Setup on Windows Server (No GUI) using PowerShell

For deploying this Dockerized application stack on a Windows Server (No GUI) environment:

1.  **Prerequisites for Windows Server:**
    *   Windows Server 2019/2022/2025 (or a version that supports Docker Engine).
    *   PowerShell 5.1 or higher.
    *   Administrative privileges for installing Docker Engine and managing system features.
    *   Git for Windows installed and accessible in the PATH.
    *   Internet connectivity for downloading Docker, Git, and Docker images.

2.  **Download the Setup Script:**
    *   Download the `setup-windows-server.ps1` script from this repository to your Windows Server.

3.  **Run the Script:**
    *   Open PowerShell **as Administrator**.
    *   Navigate to the directory where you saved the script.
    *   You may need to adjust PowerShell's execution policy to run the script:
        ```powershell
        Set-ExecutionPolicy RemoteSigned -Scope Process -Force
        # Or consult your organization's policy. 'Unrestricted' is less secure.
        ```
    *   Run the script:
        ```powershell
        .\setup-windows-server.ps1
        ```

4.  **Follow Script Prompts:**
    *   The script will check for Docker and Git. If not found, it will display detailed instructions on how to install them manually. **You will need to follow these instructions and potentially restart your server if prompted by the Docker installation.**
    *   It will ask for the Git repository URL (you can usually accept the default if the script has the correct one) and a local path to clone the project.
    *   After cloning, it will create initial `.env` files from templates.

5.  **Manual Configuration (Crucial):**
    *   Once the script prompts you, **manually edit** the following files with your specific settings:
        *   `.env` (in the project root, for Docker Compose level settings if any).
        *   `backend_assistant\.env.assistant` (for IMAP, InvoiceNinja API token, Google credentials, Webhook URL, etc.).
        *   `backend_assistant\config\client_billing_rates.json` (for client-specific billing rates).
    *   Refer to `backend_assistant/README.md` for detailed guidance on these configurations, especially for obtaining Google OAuth refresh tokens.

6.  **Complete Setup with Script:**
    *   After configuring the files, confirm in the script to proceed.
    *   The script will then run `docker-compose pull` and `docker-compose up -d --build` to download images, build the assistant, and start all services.

7.  **Post-Setup:**
    *   The script will display URLs to access the services and common `docker-compose` commands for management.

## Backend Assistant API Endpoints

The assistant provides the following API endpoints (base URL: `http://localhost:8001`):

*   `GET /health`: Health check.
*   `POST /control/start_monitoring`: Starts the email monitoring service.
*   `POST /control/stop_monitoring`: Stops the email monitoring service.
*   `GET /control/status`: Gets the current status of the email monitoring service.
*   `GET /logs?limit=100&offset=0`: Retrieves event logs from the assistant's database.
*   `WEBSOCKET /ws/status`: WebSocket endpoint for real-time status updates.

## Configuration Details

*   **Service Orchestration**: Managed by `docker-compose.yml`. This file defines all services, volumes, networks, and their configurations.
*   **Backend Assistant**: See `backend_assistant/README.md` for comprehensive configuration details, including IMAP, InvoiceNinja, Google Calendar (OAuth setup), Webhook URL, and the client billing rates JSON format.
*   **InvoiceNinja**: Runs on SQLite. Data is persisted in Docker volumes. `APP_KEY` in `docker-compose.yml` is critical; do not change it after initial setup unless you know what you're doing.
*   **OpenWebUI**: Configured in `docker-compose.yml` to connect to the backend assistant and potentially a local LLM.

## Development (Backend Assistant)

1.  **Navigate to `backend_assistant` directory.**
    ```bash
    cd backend_assistant
    ```
2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```
3.  **Install dependencies using Poetry:**
    ```bash
    pip install poetry # If not already installed
    poetry install
    ```
4.  **Set up `.env.assistant`** as described in Quick Start.
5.  **Run the application locally (for development):**
    ```bash
    poetry run uvicorn app.main:app --reload --port 8001
    ```

### Testing (Backend Assistant)

1.  Ensure development dependencies are installed (`poetry install --with dev`).
2.  Run tests using pytest:
    ```bash
    cd backend_assistant
    poetry run pytest
    ```

## Architecture Overview

*   **`docker-compose.yml`**: Orchestrates all services: `nginx` (for InvoiceNinja UI), `invoiceninja`, `backend_assistant`, `open-webui`, and optionally an `llm-runner`.
*   **`backend_assistant/`**: Contains the Python FastAPI application for the assistant.
    *   **`Dockerfile`**: Defines how the assistant's Docker image is built.
    *   **`pyproject.toml`**: Manages Python dependencies using Poetry.
    *   **`app/`**: Source code for the assistant.
        *   **`main.py`**: FastAPI application, API endpoints, WebSocket.
        *   **`config.py`**: Pydantic-based settings management.
        *   **`database.py`**: SQLite database setup and logging functions.
        *   **`email_handler.py`**: IMAP connection, email fetching, parsing, archiving. Manages workflow.
        *   **`data_extractor.py`**: Logic for extracting specific information from emails.
        *   **`invoiceninja_client.py`**: Client for interacting with the InvoiceNinja API.
        *   **`calendar_handler.py`**: Client for interacting with Google Calendar API.
        *   **`notification_handler.py`**: Sends notifications to webhook URL.
        *   **`utils.py`**: Utility functions (e.g., retry decorators).
    *   **`tests/`**: Unit tests for the assistant.
    *   **`config/`**: Directory for configuration files like `client_billing_rates.json` (mounted into container).

## Troubleshooting

*   **General Docker Issues**:
    *   Ensure Docker and Docker Compose are up to date.
    *   Check logs for all services: `docker-compose logs -f`
    *   For specific service: `docker-compose logs backend_assistant` (or `invoiceninja`, `openwebui`).
*   **Backend Assistant Startup**:
    *   Verify all required environment variables in `backend_assistant/.env.assistant` are correctly set.
    *   Check for errors in `backend_assistant/config/client_billing_rates.json` if used.
*   **Email Processing**:
    *   See `backend_assistant/README.md` for detailed troubleshooting on IMAP, InvoiceNinja, and Google Calendar.
    *   Use the `/logs` endpoint of the assistant or check its Docker logs.
*   **InvoiceNinja**:
    *   Ensure the `APP_KEY` in `docker-compose.yml` is stable. Changing it can lead to issues.
    *   Check `docker-compose logs invoiceninja`.
*   **OpenWebUI**:
    *   Ensure `OPENAI_API_BASE_URL` in `docker-compose.yml` for the `open-webui` service correctly points to your LLM service.
    *   Verify `BACKEND_ASSISTANT_URL` points to `http://backend_assistant:8001`.

## License

This project is licensed under the MIT License. See the `LICENSE` file if one was included (assuming MIT if not specified).
```
