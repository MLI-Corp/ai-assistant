# AI-Powered Invoice Processing System

This system combines Invoice Ninja with AI to automatically process emails, extract invoice information using GPT-2 Large, and create invoices automatically.

## Features

- **Email Monitoring**: Monitors specified email accounts for invoice requests
- **AI-Powered Processing**: Uses GPT-2 Large to understand and extract invoice details from emails
- **Automatic Invoice Generation**: Creates invoices in Invoice Ninja without manual intervention
- **Email Notifications**: Sends confirmation emails with invoice details
- **REST API**: Provides endpoints for integration and monitoring

## Prerequisites

- Docker and Docker Compose
- Python 3.9+
- Access to an email account (IMAP)
- Invoice Ninja API token

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd invoiceninja_ai
   ```

2. **Set up environment variables**
   ```bash
   cp .env.template .env
   ```
   Edit the `.env` file with your configuration.

3. **Build and start services**
   ```bash
   docker-compose up -d --build
   ```

4. **Access the services**
   - Invoice Ninja: http://localhost:9000
   - AI Assistant API: http://localhost:8000/docs

## Configuration

### Environment Variables

Create a `.env` file based on `.env.template` with the following variables:

```
# Email Configuration
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-specific-password

# InvoiceNinja Configuration
INVOICE_NINJA_TOKEN=your-invoice-ninja-token

# Model Configuration
MODEL_PATH=./gpt-large
MAX_INPUT_LENGTH=1024
MAX_GENERATION_LENGTH=500

# Application Settings
POLL_INTERVAL=300  # 5 minutes
```

### Email Setup

For Gmail, you'll need to:
1. Enable 2-Step Verification
2. Generate an App Password
3. Use the App Password in the `EMAIL_PASSWORD` field

## API Endpoints

- `GET /` - Welcome message
- `POST /process-emails` - Manually trigger email processing
- `GET /health` - Health check endpoint

## Development

### Running Locally

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

### Testing

Run the test script to verify the AI model:
```bash
python test_model.py
```

## Architecture

- **app/email_processor.py**: Handles email retrieval and processing
- **app/llm_processor.py**: Processes email content using GPT-2 Large
- **app/invoice_generator.py**: Interfaces with Invoice Ninja API
- **app/main.py**: FastAPI application with endpoints

## Troubleshooting

- **Email not being processed**: Check the logs with `docker-compose logs ai-assistant`
- **Model not loading**: Ensure the model files are in the `gpt-large` directory
- **API connection issues**: Verify the Invoice Ninja URL and token

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
