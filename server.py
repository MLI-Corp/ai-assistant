import uvicorn
from fastapi import FastAPI
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import os
from huggingface_hub import login

app = FastAPI()

# Set environment variables
os.environ['HF_API_TOKEN'] = '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'

# Configure model settings
model_name = "distilgpt2"  # Smaller and more reliable model

# Global variables for model and tokenizer
model = None
tokenizer = None

@app.on_event("startup")
def startup_event():
    global model, tokenizer
    try:
        print("Starting model loading...")
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

    except Exception as e:
        print(f"Error loading model: {str(e)}")
        raise

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/generate")
def generate(text: str):
    if not model or not tokenizer:
        return {"error": "Model not loaded"}
    
    try:
        inputs = tokenizer(text, return_tensors="pt")
        outputs = model.generate(
            **inputs,
            max_length=64,
            num_return_sequences=1,
            do_sample=True,
            temperature=0.7
        )
        result = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
