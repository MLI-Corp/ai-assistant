import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "InvoiceNinja AI Assistant"
    
    # Email Configuration
    EMAIL_SERVER: str = os.getenv("EMAIL_SERVER", "imap.gmail.com")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", 993))
    EMAIL_USERNAME: str = os.getenv("EMAIL_USERNAME", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
    EMAIL_FOLDER: str = os.getenv("EMAIL_FOLDER", "INBOX")
    
    # InvoiceNinja Configuration
    INVOICE_NINJA_URL: str = os.getenv("INVOICE_NINJA_URL", "http://invoiceninja:80")
    INVOICE_NINJA_TOKEN: str = os.getenv("INVOICE_NINJA_TOKEN", "")
    
    # LLM Configuration
    LLM_API_BASE_URL: str = os.getenv("LLM_API_BASE_URL", "http://localhost:12434/v1API")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "meta-llama/Meta-Llama-3.2-70B")
    LLM_BACKEND: str = os.getenv("LLM_BACKEND", "http")  # or "airllm", "transformers"
    
    # Model Configuration (Transformers)
    MODEL_PATH: str = os.getenv("MODEL_PATH", "./gpt-large")
    MAX_INPUT_LENGTH: int = int(os.getenv("MAX_INPUT_LENGTH", 1024))
    MAX_GENERATION_LENGTH: int = int(os.getenv("MAX_GENERATION_LENGTH", 500))
    
    # AirLLM Configuration
    MODEL_NAME: str = os.getenv("MODEL_NAME", "TheBloke/Llama-2-7B-Chat-AWQ")  # Example model
    MODEL_CACHE_DIR: str = os.getenv("MODEL_CACHE_DIR", "./model_cache")
    MODEL_OFFLOAD_DIR: str = os.getenv("MODEL_OFFLOAD_DIR", "./offload")
    TRUST_REMOTE_CODE: bool = os.getenv("TRUST_REMOTE_CODE", "true").lower() == "true"
    TORCH_DTYPE: str = os.getenv("TORCH_DTYPE", "auto")  # float16, bfloat16, float32, or auto
    MAX_SEQ_LENGTH: int = int(os.getenv("MAX_SEQ_LENGTH", 4096))
    USE_GPU: bool = os.getenv("USE_GPU", "true").lower() == "true"
    GPU_MEMORY_UTILIZATION: float = float(os.getenv("GPU_MEMORY_UTILIZATION", "0.9"))
    OFFLOAD_LAYERS_RATIO: float = float(os.getenv("OFFLOAD_LAYERS_RATIO", "0.7"))
    OFFLOAD_LAYERS_BUFFER: int = int(os.getenv("OFFLOAD_LAYERS_BUFFER", "4"))
    USE_SAFETENSORS: bool = os.getenv("USE_SAFETENSORS", "true").lower() == "true"
    USE_FLASH_ATTENTION: bool = os.getenv("USE_FLASH_ATTENTION", "false").lower() == "true"
    
    # Email Monitoring Settings
    ENABLE_EMAIL_MONITORING: bool = os.getenv("ENABLE_EMAIL_MONITORING", "true").lower() == "true"
    EMAIL_CHECK_INTERVAL: int = int(os.getenv("EMAIL_CHECK_INTERVAL", "300"))  # 5 minutes
    
    # Application Settings
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "300"))  # 5 minutes
    
    class Config:
        case_sensitive = True

settings = Settings()
