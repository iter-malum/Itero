# test_fine_tuned_model.py
from model_loader import load_peft_model
import torch

def test_rule_generation():
    """Тестирует генерацию правил дообученной моделью"""
    
    # Загружаем модель
    model, tokenizer = load_peft_model(
        "codellama/CodeLlama-7b-hf",
        "outputs/codeLlama-7b-semgrep-lora"
    )
    
    # Тестовый промпт
    test_prompt = """<s>[INST] Ты - эксперт по безопасности и статическому анализу кода. Создай правило Semgrep для обнаружения следующей уязвимости:

Описание уязвимости: Обнаружение SQL-инъекции через конкатенацию строк
Пример кода с уязвимостью:
```python
query = "SELECT * FROM users WHERE id = " + user_inputСоздай точное и эффективное правило Semgrep в формате YAML. Верни только YAML-правило без дополнительных комментариев. [/INST]"""
    # Генерация
    inputs = tokenizer(test_prompt, return_tensors="pt", max_length=2048, truncation=True)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print("Сгенерированное правило:")
    print(response)

if __name__ == "__main__":
    test_rule_generation()