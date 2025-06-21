import logging
import os
from typing import List, Dict, Any, Optional
from airllm import AirLLMLlama2, AirLLMChatGLM, AirLLMQWen
from .config import settings

logger = logging.getLogger(__name__)

class AirLLMProcessor:
    def __init__(self):
        """Initialize the AirLLM processor with configuration from settings."""
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if settings.USE_GPU else "cpu"
        self.initialize_model()
    
    def initialize_model(self):
        """Initialize the AirLLM model with the specified configuration."""
        try:
            logger.info(f"Initializing AirLLM with model: {settings.MODEL_NAME}")
            
            # Determine model type from model name or path
            model_name_lower = settings.MODEL_NAME.lower()
            if 'chatglm' in model_name_lower:
                model_class = AirLLMChatGLM
            elif 'qwen' in model_name_lower:
                model_class = AirLLMQWen
            else:
                # Default to Llama2 for other models
                model_class = AirLLMLlama2
            
            logger.info(f"Using AirLLM model class: {model_class.__name__}")
            
            # Initialize the appropriate AirLLM class
            self.model = model_class(
                model_name=settings.MODEL_NAME,
                cache_dir=settings.MODEL_CACHE_DIR,
                offload_folder=settings.MODEL_OFFLOAD_DIR,
                trust_remote_code=settings.TRUST_REMOTE_CODE,
                device_map="auto" if self.device == "cuda" else "cpu",
                torch_dtype=settings.TORCH_DTYPE,
                max_seq_len=settings.MAX_SEQ_LENGTH,
                gpu_memory_utilization=settings.GPU_MEMORY_UTILIZATION,
                offload_layers_ratio=settings.OFFLOAD_LAYERS_RATIO,
                offload_layers_buffer=settings.OFFLOAD_LAYERS_BUFFER,
                use_safetensors=settings.USE_SAFETENSORS,
                use_flash_attention=settings.USE_FLASH_ATTENTION,
            )
            
            logger.info("AirLLM model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AirLLM model: {str(e)}")
            raise
    
    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1,
        do_sample: bool = True,
        **kwargs
    ) -> str:
        """
        Generate text using the AirLLM model.
        
        Args:
            prompt: The input prompt
            max_new_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            repetition_penalty: Penalty for repeating tokens
            do_sample: Whether to use sampling
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text
        """
        try:
            generation_params = {
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "repetition_penalty": repetition_penalty,
                "do_sample": do_sample,
                **kwargs
            }
            
            # Generate response
            output = self.model.generate(
                prompt,
                **generation_params
            )
            
            # Extract the generated text (remove the input prompt)
            generated_text = output[0][len(prompt):].strip()
            return generated_text
            
        except Exception as e:
            logger.error(f"Error during text generation: {str(e)}")
            raise
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a chat response based on conversation history.
        
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
            # Format messages into a single prompt
            prompt = self._format_chat_prompt(messages)
            
            # Generate response
            response_text = self.generate(
                prompt=prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                **kwargs
            )
            
            return {
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "model": settings.MODEL_NAME,
                "usage": {
                    "prompt_tokens": len(self.model.tokenizer.encode(prompt)),
                    "completion_tokens": len(self.model.tokenizer.encode(response_text)),
                    "total_tokens": 0  # Will be calculated in the response
                }
            }
            
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            raise
    
    def _format_chat_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        Format chat messages into a single prompt string.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            
        Returns:
            Formatted prompt string
        """
        formatted_prompt = ""
        for message in messages:
            role = message.get('role', 'user')
            content = message.get('content', '').strip()
            
            if role == 'system':
                formatted_prompt += f"System: {content}\n\n"
            elif role == 'user':
                formatted_prompt += f"User: {content}\n"
            elif role == 'assistant':
                formatted_prompt += f"Assistant: {content}\n"
        
        # Add assistant prefix for the next response
        formatted_prompt += "Assistant: "
        return formatted_prompt
