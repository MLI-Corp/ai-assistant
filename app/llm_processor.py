import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline, StoppingCriteria, StoppingCriteriaList
import json
import logging
from typing import Dict, Any, List, Optional
from .config import settings

logger = logging.getLogger(__name__)

class StopOnTokens(StoppingCriteria):
    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        stop_ids = [50256]  # End-of-text token for GPT-2
        return input_ids[0][-1] in stop_ids

class LLMProcessor:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing LLMProcessor with device: {self.device}")
        
        # Load tokenizer and model
        logger.info("Loading tokenizer and model...")
        self.tokenizer = AutoTokenizer.from_pretrained(settings.MODEL_PATH)
        self.model = AutoModelForCausalLM.from_pretrained(settings.MODEL_PATH).to(self.device)
        self.model.eval()
        logger.info("Model and tokenizer loaded successfully")
        
        # Conversation history
        self.conversation_history = []
    
    def format_chat_prompt(self, messages):
        """Format messages into a single prompt string."""
        formatted_prompt = ""
        for message in messages:
            role = message.role
            content = message.content
            if role == "user":
                formatted_prompt += f"User: {content}\n"
            else:
                formatted_prompt += f"Assistant: {content}\n"
        formatted_prompt += "Assistant: "
        return formatted_prompt
    
    def chat(self, messages, max_length=200, temperature=0.7, top_p=0.9):
        """
        Generate a chat response based on the conversation history.
        
        Args:
            messages: List of chat messages
            max_length: Maximum length of the generated response
            temperature: Controls randomness (lower = more deterministic)
            top_p: Nucleus sampling parameter
            
        Returns:
            Dictionary containing the generated response and metadata
        """
        try:
            # Format the chat history into a prompt
            prompt = self.format_chat_prompt(messages)
            
            # Encode the prompt
            inputs = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
            
            # Generate response
            stopping_criteria = StoppingCriteriaList([StopOnTokens()])
            
            outputs = self.model.generate(
                inputs,
                max_length=min(max_length + len(inputs[0]), 1024),  # Respect model's max length
                temperature=temperature,
                top_p=top_p,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                stopping_criteria=stopping_criteria
            )
            
            # Decode the response
            full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Extract only the assistant's response
            assistant_response = full_response[len(prompt):].strip()
            
            # Calculate token usage
            prompt_tokens = len(inputs[0])
            completion_tokens = len(self.tokenizer.encode(assistant_response))
            
            return {
                "message": {
                    "role": "assistant",
                    "content": assistant_response
                },
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                },
                "model": "gpt2-large"
            }
            
        except Exception as e:
            logger.error(f"Error in chat generation: {str(e)}")
            raise
    
    def process_email(self, email_content: str) -> Dict[str, Any]:
        """
        Process an email and extract invoice information using the LLM.
        
        Args:
            email_content: The content of the email to process
            
        Returns:
            Dict containing extracted invoice information
        """
        try:
            # Create a prompt for the model
            prompt = f"""Extract the following information from this email to create an invoice. 
            If information is missing, use reasonable defaults. Respond in JSON format with these fields:
            - client_name: str
            - client_email: str
            - items: List[dict] with keys: description, quantity, price
            - due_date: str (YYYY-MM-DD)
            - notes: str
            
            Email content:
            {email_content}
            
            JSON Response:
            """
            
            # Tokenize the prompt
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                max_length=settings.MAX_INPUT_LENGTH,
                truncation=True
            ).to(self.device)
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=settings.MAX_GENERATION_LENGTH,
                    num_return_sequences=1,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode the response
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Extract JSON from the response
            try:
                # Find the start and end of the JSON object
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    import json
                    return json.loads(json_str)
                else:
                    logger.error("Could not find valid JSON in model response")
                    return {}
                    
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON response: {e}")
                return {}
                
        except Exception as e:
            logger.error(f"Error processing email with LLM: {str(e)}")
            raise
