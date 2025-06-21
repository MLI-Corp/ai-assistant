from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch
import time

def test_gpt2_cpu():
    print("Loading GPT-2 Large model...")
    start_time = time.time()
    
    # Ensure we're using CPU
    device = torch.device("cpu")
    print(f"Using device: {device}")
    
    # Load the model and tokenizer from local directory
    model_path = "./gpt-large"
    print(f"Loading model from: {model_path}")
    
    try:
        # Load tokenizer and model
        tokenizer = GPT2Tokenizer.from_pretrained(model_path)
        model = GPT2LMHeadModel.from_pretrained(model_path).to(device)
        
        # Print model info
        print("\nModel loaded successfully!")
        print(f"Model device: {next(model.parameters()).device}")
        print(f"Model parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")
        
        # Test inference
        print("\nTesting inference...")
        prompt = "Once upon a time"
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_length=50,
                num_return_sequences=1,
                temperature=0.7,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )
        
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print("\nGenerated text:")
        print(generated_text)
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        raise
    
    finally:
        print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    test_gpt2_cpu()
