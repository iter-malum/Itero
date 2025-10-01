#!/usr/bin/env python3
"""
Скрипт для генерации правил с помощью обученной модели
Теперь с поддержкой формата инструкций
"""
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    pipeline
)
from peft import PeftModel, PeftConfig
import yaml
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_model(model_path):
    """Загружает обученную модель"""
    try:
        # Загружаем базовую модель
        model = AutoModelForCausalLM.from_pretrained(
            "codellama/CodeLlama-7b-hf",
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        
        # Загружаем адаптеры LoRA
        model = PeftModel.from_pretrained(model, model_path)
        model = model.merge_and_unload()
        
        # Загружаем токенизатор
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        tokenizer.pad_token = tokenizer.eos_token
        
        return model, tokenizer
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке модели: {str(e)}")
        raise

def generate_rule(model, tokenizer, prompt, max_length=1024):
    """Генерирует правило на основе промпта"""
    # Форматируем промпт в стиле инструкции
    formatted_prompt = f"<s>[INST] Напиши правило Semgrep для обнаружения следующей проблемы:\n{prompt}\n[/INST]"
    
    # Генерируем ответ
    inputs = tokenizer(formatted_prompt, return_tensors="pt")
    
    with torch.no_grad():
        outputs = model.generate(
            inputs.input_ids,
            max_length=max_length,
            num_return_sequences=1,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    
    # Декодируем результат
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Извлекаем сгенерированное правило (часть после [/INST])
    if "[/INST]" in generated_text:
        generated_text = generated_text.split("[/INST]")[1].strip()
    
    # Удаляем возможные теги
    generated_text = generated_text.replace("</s>", "").strip()
    
    return generated_text

def validate_rule(rule_text):
    """Проверяет валидность сгенерированного правила"""
    try:
        # Пробуем распарсить YAML
        rule_data = yaml.safe_load(rule_text)
        
        if not rule_data or 'rules' not in rule_data:
            return False, "Не содержит секции rules"
            
        rule = rule_data['rules'][0]
        required_fields = ['id', 'message', 'languages', 'severity']
        
        for field in required_fields:
            if field not in rule:
                return False, f"Отсутствует обязательное поле: {field}"
                
        return True, "Валидное правило"
        
    except yaml.YAMLError as e:
        return False, f"Ошибка YAML: {str(e)}"
    except Exception as e:
        return False, f"Неожиданная ошибка: {str(e)}"

def test_generation(model, tokenizer):
    """Тестирует генерацию на нескольких примерах"""
    test_cases = [
        """На языке Python найди проблему: Использование устаревшей функции ssl.wrap_socket
Уязвимый код:
```python
import ssl
sock = ssl.wrap_socket(sock, ssl_version=ssl.PROTOCOL_SSLv2)
```""",
        """На языке Terraform найди проблему: Открытый доступ к S3 bucket через политику
Уязвимый код:
```hcl
resource "aws_s3_bucket" "example" {
  bucket = "my-tf-test-bucket"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = "*"
        Action = "s3:*"
        Resource = "arn:aws:s3:::my-tf-test-bucket/*"
      }
    ]
  })
}
```"""
    ]
    
    for i, test_prompt in enumerate(test_cases):
        logger.info(f"=== Тест {i+1} ===")
        logger.info(f"Промпт: {test_prompt[:200]}...")
        
        # Генерируем правило
        generated_rule = generate_rule(model, tokenizer, test_prompt)
        
        logger.info("Сгенерированное правило:")
        logger.info(f"```yaml\n{generated_rule}\n```")
        
        # Проверяем валидность
        is_valid, message = validate_rule(generated_rule)
        logger.info(f"Валидность правила: {is_valid}, Сообщение: {message}")
        logger.info("")

def main():
    """Основная функция генерации"""
    try:
        # Загружаем модель
        model_path = "../outputs/codeLlama-7b-semgrep-lora"
        logger.info(f"Загружаем модель из: {model_path}")
        model, tokenizer = load_model(model_path)
        
        # Тестируем генерацию
        test_generation(model, tokenizer)
        
    except Exception as e:
        logger.error(f"Ошибка при генерации правила: {str(e)}")

if __name__ == "__main__":
    main()