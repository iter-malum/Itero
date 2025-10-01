#!/usr/bin/env python3
"""
Скрипт для отладки процесса обучения.
Проверяет данные, модель и процесс обучения перед запуском.
"""
import torch
from transformers import AutoTokenizer
from datasets import load_dataset
import json
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_data():
    """Отладочная функция для проверки данных"""
    logger.info("=== ОТЛАДКА ДАННЫХ ===")
    
    # Загружаем данные
    dataset = load_dataset('json', data_files={'train': '../data/processed/semgrep_training_data.jsonl'})
    logger.info(f"Размер датасета: {len(dataset['train'])} примеров")
    
    # Смотрим первые несколько примеров
    for i in range(min(3, len(dataset['train']))):
        example = dataset['train'][i]
        logger.info(f"Пример {i + 1}:")
        logger.info(f"Промпт: {example['prompt'][:200]}...")
        logger.info(f"Completion: {example['completion'][:200]}...")
        logger.info("---")
    
    return dataset

def debug_model():
    """Отладочная функция для проверки модели"""
    logger.info("=== ОТЛАДКА МОДЕЛИ ===")
    
    # Проверяем доступность GPU
    logger.info(f"Доступно CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        logger.info(f"Количество GPU: {torch.cuda.device_count()}")
        logger.info(f"Текущее устройство: {torch.cuda.current_device()}")
        logger.info(f"Имя устройства: {torch.cuda.get_device_name()}")
    
    # Проверяем доступность памяти
    for i in range(torch.cuda.device_count()):
        logger.info(f"GPU {i}: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.2f} GB")
    
    # Пробуем загрузить токенизатор
    try:
        tokenizer = AutoTokenizer.from_pretrained("codellama/CodeLlama-7b-hf")
        tokenizer.pad_token = tokenizer.eos_token
        logger.info("Токенизатор успешно загружен")
        return tokenizer
    except Exception as e:
        logger.error(f"Ошибка при загрузке токенизатора: {str(e)}")
        return None

def debug_tokenization(tokenizer):
    """Отладочная функция для проверки токенизации"""
    logger.info("=== ОТЛАДКА ТОКЕНИЗАЦИИ ===")
    
    # Тестовый пример
    test_examples = [
        "На языке Python найди проблему: Использование устаревшей функции ssl.wrap_socket",
        "На языке Terraform найди проблему: Открытый доступ к S3 bucket через политику"
    ]
    
    for i, example in enumerate(test_examples):
        tokens = tokenizer.encode(example)
        logger.info(f"Пример {i + 1}: {len(tokens)} токенов")
        logger.info(f"Токены: {tokens[:10]}...")  # Первые 10 токенов
        
        # Декодируем обратно для проверки
        decoded = tokenizer.decode(tokens[:10])
        logger.info(f"Декодировано: {decoded}")
        logger.info("---")

if __name__ == "__main__":
    logger.info("Запуск отладочного скрипта")
    
    # Проверяем данные
    dataset = debug_data()
    
    # Проверяем модель и оборудование
    tokenizer = debug_model()
    
    if tokenizer:
        # Проверяем токенизацию
        debug_tokenization(tokenizer)
    
    logger.info("Отладочный скрипт завершен")