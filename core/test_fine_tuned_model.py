# core/test_fine_tuned_model_fixed.py
from model_loader import load_peft_model_simple
import torch

def test_rule_generation():
    """Тестирует генерацию правил дообученной моделью"""
    
    print("🔧 Загрузка дообученной модели...")
    
    # Загружаем модель
    model, tokenizer = load_peft_model_simple(
        "codellama/CodeLlama-7b-hf",
        "outputs/codeLlama-7b-semgrep-lora"
    )
    
    print("✅ Модель загружена. Тестируем генерацию правила...")
    
    # Правильный промпт для CodeLlama
    test_prompt = """[INST] <<SYS>>
    Ты - эксперт по безопасности и статическому анализу кода. Создай правило Semgrep для обнаружения SQL-инъекций через конкатенацию строк в Python.
    <</SYS>>

    Создай правило Semgrep для обнаружения следующей уязвимости:

    Описание: SQL-инъекция через конкатенацию строк
    Пример уязвимого кода:
    ```python
    query = "SELECT * FROM users WHERE id = " + user_input```
    Создай точное правило Semgrep в формате YAML. Верни ТОЛЬКО YAML-код без дополнительных комментариев. [/INST]"""

    print("🔄 Генерация правила...")
    
    # Токенизация с правильной обработкой
    inputs = tokenizer(test_prompt, return_tensors="pt", max_length=2048, truncation=True)
    
    # Убедимся, что inputs на том же устройстве, что и модель
    device = model.device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    # Генерация с оптимизированными параметрами
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.3,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.1,
            no_repeat_ngram_size=3
        )
    
    # Декодируем только сгенерированную часть (исключая промпт)
    generated_tokens = outputs[0][inputs['input_ids'].shape[1]:]
    response = tokenizer.decode(generated_tokens, skip_special_tokens=True)
    
    print("=" * 60)
    print("🎯 СГЕНЕРИРОВАННОЕ ПРАВИЛО:")
    print("=" * 60)
    print(response)
    print("=" * 60)
    
    # Проверяем, есть ли YAML в ответе
    if "rules:" in response or "id:" in response:
        print("✅ Правило содержит YAML-структуру")
    else:
        print("❌ YAML-структура не обнаружена")
    
    return response

if __name__ == "__main__":
    test_rule_generation()