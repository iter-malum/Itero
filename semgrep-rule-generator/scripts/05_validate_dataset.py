#!/usr/bin/env python3
"""
Скрипт для проверки качества созданного датасета
"""
import json
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_dataset():
    """Проверяет созданный датасет"""
    dataset_path = Path("../data/processed/semgrep_training_data.jsonl")
    
    if not dataset_path.exists():
        logger.error("Датасет не найден")
        return
        
    examples = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                example = json.loads(line)
                examples.append(example)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка JSON в строке {line_num}: {e}")
                
    logger.info(f"Всего валидных примеров: {len(examples)}")
    
    # Анализируем распределение
    languages = {}
    for example in examples[:100]:  # Проверяем первые 100 примеров
        prompt = example.get('prompt', '')
        if "На языке" in prompt:
            first_line = prompt.split('\n')[0]
            lang_part = first_line.replace("На языке", "").split("найди проблему")[0].strip()
            languages[lang_part] = languages.get(lang_part, 0) + 1
    
    logger.info("Распределение языков в примерах:")
    for lang, count in languages.items():
        logger.info(f"  {lang}: {count} примеров")
    
    # Проверяем несколько примеров
    for i, example in enumerate(examples[:3]):
        logger.info(f"=== Пример {i+1} ===")
        logger.info(f"Промпт: {example['prompt'][:200]}...")
        logger.info(f"Completion: {example['completion'][:200]}...")
        logger.info("")

if __name__ == "__main__":
    validate_dataset()