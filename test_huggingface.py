import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import os
from huggingface_hub import login

# Set environment variables
os.environ['HF_API_TOKEN'] = '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'
os.environ['HUGGING_FACE_HUB_TOKEN'] = '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'

# Configure model settings
model_name = "distilgpt2"  # Smaller and more reliable model

def load_model():
    try:
        print("Starting model download...")
        # Login to Hugging Face
        login(token=os.environ['HF_API_TOKEN'])
        print("Logged in to Hugging Face")

        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            use_auth_token=os.environ['HF_API_TOKEN'],
            local_files_only=False
        )
        print("Tokenizer loaded successfully")

        # Load model
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,  # Using float32 for better compatibility
            device_map="auto",
            use_auth_token=os.environ['HF_API_TOKEN'],
            local_files_only=False
        )
        print("Model loaded successfully")
        return model, tokenizer
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        model, tokenizer = load_model()
        print("Model and tokenizer loaded successfully!")
    except Exception as e:
        print(f"Final error: {str(e)}")
        print("\nDetailed error information:")
        import traceback
        traceback.print_exc()
