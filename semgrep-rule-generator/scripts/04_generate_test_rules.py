    #!/usr/bin/env python3
"""
Скрипт для тестирования обработки конкретного правила.
Полезен для отладки обработки сложных случаев.
"""
import yaml
import json
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_specific_rule(rule_path):
    """Тестирует обработку конкретного правила"""
    from scripts_02_process_to_jsonl import parse_rule_file, find_test_file, extract_annotated_code, create_training_examples
    
    rule_info = parse_rule_file(rule_path)
    if not rule_info:
        logger.error("Не удалось распарсить правило")
        return
        
    logger.info(f"Обрабатываем правило: {rule_info['id']}")
    logger.info(f"Языки: {rule_info['languages']}")
    
    # Ищем тестовый файл
    test_file = find_test_file(rule_path, rule_info['languages'])
    if not test_file:
        logger.error("Тестовый файл не найден")
        return
        
    logger.info(f"Найден тестовый файл: {test_file}")
    
    # Читаем тестовый файл
    with open(test_file, 'r', encoding='utf-8') as f:
        test_content = f.read()
        
    # Извлекаем аннотированный код
    annotated_sections = extract_annotated_code(test_content, rule_info['id'])
    logger.info(f"Найдено bad примеров: {len(annotated_sections['bad'])}")
    logger.info(f"Найдено good примеров: {len(annotated_sections['good'])}")
    
    # Создаем примеры для обучения
    examples = create_training_examples(rule_info, test_content)
    logger.info(f"Создано примеров для обучения: {len(examples)}")
    
    # Показываем первый пример
    if examples:
        logger.info("=== ПЕРВЫЙ ПРОМПТ ===")
        logger.info(examples[0]['prompt'])
        logger.info("=== ПЕРВОЕ COMPLETION ===")
        logger.info(examples[0]['completion'])

if __name__ == "__main__":
    # Пример использования: python 04_generate_test_rules.py semgrep-rules/csharp/dotnet/security/mvc-missing-antiforgery.yaml
    import sys
    if len(sys.argv) > 1:
        rule_path = Path(sys.argv[1])
        if rule_path.exists():
            test_specific_rule(rule_path)
        else:
            logger.error("Файл не существует")
    else:
        logger.error("Укажите путь к правилу в аргументах командной строки")