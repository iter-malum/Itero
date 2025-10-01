#!/usr/bin/env python3
"""
Скрипт для проверки созданного датасета.
Показывает примеры и статистику.
"""
import json
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def inspect_dataset():
    """Проверяет созданный датасет"""
    dataset_path = Path("../data/processed/semgrep_training_data.jsonl")
    
    if not dataset_path.exists():
        logger.error("Датасет не найден. Сначала запустите 02_process_to_jsonl.py")
        return
        
    examples = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line in f:
            examples.append(json.loads(line))
            
    logger.info(f"Всего примеров в датасете: {len(examples)}")
    
    # Показываем первые несколько примеров
    for i, example in enumerate(examples[:3]):
        logger.info(f"=== Пример {i+1} ===")
        logger.info(f"Промпт (первые 200 символов): {example['prompt'][:200]}...")
        logger.info(f"Completion (первые 200 символов): {example['completion'][:200]}...")
        logger.info("")
        
    # Анализируем распределение языков
    languages = {}
    for example in examples:
        # Извлекаем язык из промпта
        if "На языке" in example['prompt']:
            lang_line = example['prompt'].split("\n")[0]
            lang = lang_line.replace("На языке", "").split("найди проблему")[0].strip()
            languages[lang] = languages.get(lang, 0) + 1
            
    logger.info("Распределение языков:")
    for lang, count in languages.items():
        logger.info(f"  {lang}: {count} примеров")

if __name__ == "__main__":
    inspect_dataset()