import typer
import requests
from typing import Optional, List, Dict, Any
import json
from pathlib import Path
import sys
from datetime import datetime
import docker
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
import time

app = typer.Typer()
console = Console()

# Configuration
INVOICE_NINJA_URL = "http://invoiceninja:80"
INVOICE_NINJA_TOKEN = "your_api_token_here"  # Will be loaded from environment
MODEL_API_URL = "http://llama-server/v1"

# Initialize Docker client
try:
    docker_client = docker.from_env()
except Exception as e:
    console.print(f"[red]Error initializing Docker client: {e}[/red]")
    docker_client = None

# Initialize HTTP client with auth
headers = {
    "X-Ninja-Token": INVOICE_NINJA_TOKEN,
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest"
}

def call_model(prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
    """Call the local Llama model with the given prompt"""
    try:
        response = requests.post(
            f"{MODEL_API_URL}/chat/completions",
            json={
                "model": "meta-llama/Meta-Llama-3.2-70B",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        console.print(f"[red]Error calling model: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def process_invoice(invoice_id: str):
    """Process a specific invoice with AI analysis"""
    try:
        # Get invoice data
        response = requests.get(
            f"{INVOICE_NINJA_URL}/api/v1/invoices/{invoice_id}",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        invoice = response.json()["data"]
        
        # Create AI prompt
        prompt = f"""Analyze this invoice and extract key information:
        - Client: {invoice.get('client', {}).get('name', 'N/A')}
        - Amount: {invoice.get('amount', 'N/A')}
        - Due Date: {invoice.get('due_date', 'N/A')}
        - Status: {invoice.get('status', 'N/A')}
        
        Please provide a summary and any action items."""
        
        # Get AI analysis
        with console.status("Analyzing invoice with AI..."):
            analysis = call_model(prompt)
        
        # Display results
        console.print("\n[bold]AI Analysis for Invoice:[/bold]")
        console.print("=" * 50)
        console.print(analysis)
        console.print("=" * 50)
        
    except Exception as e:
        console.print(f"[red]Error processing invoice: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def list_models():
    """List all available AI models"""
    if not docker_client:
        console.print("[red]Docker is not available[/red]")
        raise typer.Exit(1)
    
    try:
        models = []
        containers = docker_client.containers.list(filters={"label": "ai.model.runner"})
        
        if not containers:
            console.print("No model runners found")
            return
            
        table = Table(title="AI Model Runners")
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Model", style="magenta")
        table.add_column("Ports", style="yellow")
        
        for container in containers:
            model = container.labels.get('ai.model.runner.model', 'N/A')
            ports = ", ".join([f"{k}->{v[0]['HostPort']}" for k, v in container.attrs['NetworkSettings']['Ports'].items() if v])
            table.add_row(
                container.name,
                container.status,
                model,
                ports or "N/A"
            )
            
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing models: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def start_model(
    model_name: str = typer.Argument(..., help="Name of the model to start"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to expose the model on"),
    gpu: bool = typer.Option(True, help="Enable GPU support")
):
    """Start a model container"""
    if not docker_client:
        console.print("[red]Docker is not available[/red]")
        raise typer.Exit(1)
    
    try:
        # Check if model is already running
        containers = docker_client.containers.list(
            filters={"name": f"model-{model_name}"}
        )
        
        if containers:
            console.print(f"[yellow]Model '{model_name}' is already running[/yellow]")
            return
            
        # Start the model container
        container_config = {
            "image": f"ghcr.io/huggingface/text-generation-inference:latest",
            "name": f"model-{model_name}",
            "environment": {
                "MODEL_ID": model_name,
                "QUANTIZE": "bitsandbytes",
                "MAX_INPUT_LENGTH": "4096",
                "MAX_TOTAL_TOKENS": "8192"
            },
            "ports": {"80/tcp": port},
            "labels": {"ai.model.runner": "true", "ai.model.runner.model": model_name},
            "detach": True
        }
        
        if gpu:
            container_config["device_requests"] = [
                docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])
            ]
        
        with console.status(f"Starting {model_name}..."):
            container = docker_client.containers.run(**container_config)
            
        console.print(f"[green]Started {model_name} on port {port}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error starting model: {str(e)}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
