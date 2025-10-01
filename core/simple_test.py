# core/simple_test.py
from model_loader import load_peft_model_simple
import torch

def simple_test():
    """Простой тест генерации"""
    
    model, tokenizer = load_peft_model_simple(
        "codellama/CodeLlama-7b-hf",
        "outputs/codeLlama-7b-semgrep-lora"
    )
    
    # Очень простой промпт
    prompt = "[INST] Create a Semgrep rule for SQL injection in Python: [/INST]"
    
    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=200,
            temperature=0.1,
            do_sample=False  # Детерминированный вывод для теста
        )
    
    full_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    generated_part = full_response[len(prompt):].strip()
    
    print("Generated:", generated_part)

if __name__ == "__main__":
    simple_test()