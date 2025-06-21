import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from .config import settings

logger = logging.getLogger(__name__)

class LlamaProcessor:
    def __init__(self):
        """Initialize the Llama processor with configuration from settings."""
        self.client = OpenAI(
            base_url=settings.LLM_API_BASE_URL,
            api_key="no-api-key-required"
        )
        self.model_name = settings.LLM_MODEL_NAME
        logger.info(f"Initialized LlamaProcessor with model: {self.model_name}")
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a chat response using the Llama model.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            max_new_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            **kwargs: Additional generation parameters
            
        Returns:
            Dictionary containing the generated response and metadata
        """
        try:
            logger.debug(f"Sending chat request to model {self.model_name}")
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                **kwargs
            )
            
            # Extract the response message
            response_message = response.choices[0].message
            
            return {
                "message": {
                    "role": response_message.role,
                    "content": response_message.content
                },
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"Error in Llama chat completion: {str(e)}")
            raise
    
    def process_email(self, email_content: str) -> Dict[str, Any]:
        """
        Process an email and extract invoice information using the Llama model.
        
        Args:
            email_content: The content of the email to process
            
        Returns:
            Dict containing extracted invoice information
        """
        prompt = """Extract the following information from this email to create an invoice. 
        If information is missing, use reasonable defaults. Respond in JSON format with these fields:
        - client_name: str
        - client_email: str
        - items: list of dicts with 'description', 'quantity', 'unit_price'
        - due_date: str (YYYY-MM-DD)
        - notes: str
        
        Email content:
        """
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that extracts invoice information from emails."},
            {"role": "user", "content": prompt + email_content}
        ]
        
        try:
            response = self.chat(messages, temperature=0.3)
            import json
            return json.loads(response["message"]["content"])
        except Exception as e:
            logger.error(f"Error processing email with Llama: {str(e)}")
            raise
