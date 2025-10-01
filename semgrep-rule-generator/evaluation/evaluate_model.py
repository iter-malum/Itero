#!/usr/bin/env python3
"""
Скрипт для оценки обученной модели на тестовых примерах
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import json
import yaml
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_test_cases():
    """Загружает тестовые примеры для оценки"""
    test_cases = []
    test_data_path = Path("../data/processed/semgrep_training_data.jsonl")
    
    if not test_data_path.exists():
        logger.error("Тестовые данные не найдены")
        return test_cases
        
    with open(test_data_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 20:  # Ограничиваем количество тестовых примеров
                break
            test_cases.append(json.loads(line))
    
    return test_cases

def evaluate_model(model, tokenizer, test_cases):
    """Оценивает модель на тестовых примерах"""
    results = []
    
    for i, test_case in enumerate(test_cases):
        logger.info(f"Оцениваем пример {i+1}/{len(test_cases)}")
        
        # Генерируем правило
        generated_rule = generate_rule(model, tokenizer, test_case['prompt'])
        
        # Проверяем валидность
        is_valid, message = validate_rule(generated_rule)
        
        # Сравниваем с ожидаемым результатом
        expected_rule = test_case['completion'].replace('```yaml\n', '').replace('```', '').strip()
        
        results.append({
            'prompt': test_case['prompt'],
            'generated_rule': generated_rule,
            'expected_rule': expected_rule,
            'is_valid': is_valid,
            'validation_message': message,
            'is_correct': is_valid and generated_rule.strip() == expected_rule.strip()
        })
    
    return results

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
            temperature=0.1,  # Низкая температура для детерминированности
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

def main():
    """Основная функция оценки"""
    try:
        # Загружаем модель
        model_path = "../outputs/codeLlama-7b-semgrep-lora"
        logger.info(f"Загружаем модель из: {model_path}")
        
        model = AutoModelForCausalLM.from_pretrained(
            "codellama/CodeLlama-7b-hf",
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        
        model = PeftModel.from_pretrained(model, model_path)
        model = model.merge_and_unload()
        
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        tokenizer.pad_token = tokenizer.eos_token
        
        # Загружаем тестовые примеры
        test_cases = load_test_cases()
        logger.info(f"Загружено {len(test_cases)} тестовых примеров")
        
        # Оцениваем модель
        results = evaluate_model(model, tokenizer, test_cases)
        
        # Анализируем результаты
        valid_count = sum(1 for r in results if r['is_valid'])
        correct_count = sum(1 for r in results if r['is_correct'])
        
        logger.info(f"Результаты оценки:")
        logger.info(f"Валидных правил: {valid_count}/{len(results)} ({valid_count/len(results)*100:.2f}%)")
        logger.info(f"Правильных правил: {correct_count}/{len(results)} ({correct_count/len(results)*100:.2f}%)")
        
        # Сохраняем результаты
        results_dir = Path("../evaluation/results")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        results_file = results_dir / "evaluation_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Результаты сохранены в: {results_file}")
        
    except Exception as e:
        logger.error(f"Ошибка при оценке модели: {str(e)}")

if __name__ == "__main__":
    main()