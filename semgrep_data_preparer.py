import yaml
import json
import logging
from pathlib import Path
import re

# Настройка логирования
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('missing_rules.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def is_rule_file(file_path):
    """
    Проверяет, является ли файл правилом Semgrep (а не тестовым примером)
    """
    if file_path.suffix not in ['.yaml', '.yml']:
        return False
    
    # Игнорируем файлы, которые содержат в названии паттерны тестов
    test_patterns = ['.test.', '.fixed.']
    file_name = file_path.name.lower()
    
    for pattern in test_patterns:
        if pattern in file_name:
            return False
    
    return True

def find_test_files(rule_path):
    """
    Находит все тестовые файлы для правила
    """
    rule_dir = rule_path.parent
    rule_stem = rule_path.stem  # название без .yaml/.yml
    
    # Ищем все файлы, которые начинаются с названия правила
    test_files = []
    
    for test_file in rule_dir.glob(f"{rule_stem}.*"):
        # Пропускаем сам файл правила
        if test_file == rule_path:
            continue
        
        # Добавляем ВСЕ файлы с тем же именем, но другими расширениями
        # включая .test.yaml, .fixed.yaml и т.д.
        test_files.append(test_file)
    
    return test_files

def parse_semgrep_rule_and_code(rule_path, test_files):
    """
    Парсит правило Semgrep и соответствующие тестовые файлы
    """
    try:
        # Чтение и парсинг правила
        with open(rule_path, 'r', encoding='utf-8') as f:
            rule_content = f.read()
            rule_data = yaml.safe_load(rule_content)
        
        # Проверяем, что это валидное правило Semgrep
        if not rule_data or 'rules' not in rule_data or not rule_data['rules']:
            return None
        
        rule_metadata = rule_data['rules'][0]
        
        # Чтение всех тестовых файлов
        full_code = ""
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    test_content = f.read()
                    full_code += f"// File: {test_file.name}\n{test_content}\n\n"
            except Exception as e:
                logging.warning(f"Не удалось прочитать тестовый файл {test_file}: {e}")
                continue
        
        # Формирование instruction
        instruction = create_instruction(rule_metadata)
        
        # Создание элемента датасета
        dataset_item = {
            "instruction": instruction,
            "reasoning": "",
            "code_context": {
                "full_code": full_code.strip(),
                "dangerous_examples": [],
                "safe_examples": [],
                "annotation_legend": {
                    f"// ruleid:{rule_metadata['id']}": "Метка для кода, который ДОЛЖЕН срабатывать на правило (опасный пример)",
                    f"// ok:{rule_metadata['id']}": "Метка для кода, который НЕ должен срабатывать на правило (безопасный пример)"
                }
            },
            "metadata": {
                "rule_id": rule_metadata['id'],
                "language": rule_metadata['languages'][0] if rule_metadata.get('languages') else "",
                "severity": rule_metadata.get('severity', ''),
                "cwe": rule_metadata['metadata']['cwe'][0] if rule_metadata.get('metadata') and 'cwe' in rule_metadata['metadata'] else "",
                "rule_type": rule_metadata['metadata'].get('subcategory', [''])[0] if rule_metadata.get('metadata') else "",
                "mode": rule_metadata.get('mode', 'search'),
                "source_files": [str(rule_path)] + [str(f) for f in test_files]
            },
            "output": rule_content
        }
        
        return dataset_item
        
    except Exception as e:
        logging.error(f"Ошибка при обработке правила {rule_path}: {e}")
        return None

def create_instruction(rule_metadata):
    """
    Создает инструкцию на основе метаданных правила
    """
    rule_id = rule_metadata['id']
    message = rule_metadata.get('message', '')
    cwe = rule_metadata['metadata']['cwe'][0] if rule_metadata.get('metadata') and 'cwe' in rule_metadata['metadata'] else ""
    mode = rule_metadata.get('mode', 'search')
    
    instruction_parts = [
        f"Создай правило Semgrep для обнаружения {rule_id}",
        f"Описание уязвимости: {message}",
        f"CWE: {cwe}",
        f"Тип анализа: {mode}",
        f"Язык: {rule_metadata['languages'][0] if rule_metadata.get('languages') else 'unknown'}"
    ]
    
    # Добавляем информацию о source/sink/sanitizer для taint mode
    if mode == 'taint':
        if 'pattern-sources' in rule_metadata:
            instruction_parts.append("Источники (sources): определены в правиле")
        
        if 'pattern-sinks' in rule_metadata:
            instruction_parts.append("Синки (sinks): определены в правиле")
        
        if 'pattern-sanitizers' in rule_metadata:
            instruction_parts.append("Способы санитации: определены в правиле")
    
    return "\n".join(instruction_parts)

def process_semgrep_repository(repo_path, output_dir):
    """
    Рекурсивно обрабатывает весь репозиторий semgrep-rules
    """
    repo_path = Path(repo_path)
    output_dir = Path(output_dir)
    
    # Создаем выходную директорию
    output_dir.mkdir(parents=True, exist_ok=True)
    
    processed_count = 0
    skipped_count = 0
    
    # Рекурсивно ищем все YAML/YML файлы
    for rule_file in repo_path.rglob("*"):
        # Пропускаем директорию .github
        if ".github" in rule_file.parts:
            continue
            
        if not is_rule_file(rule_file):
            continue
        
        # Находим тестовые файлы
        test_files = find_test_files(rule_file)
        
        if not test_files:
            logging.warning(f"Не найдены тестовые файлы для правила: {rule_file}")
            skipped_count += 1
            continue
        
        # Парсим правило и создаем датасет
        dataset_item = parse_semgrep_rule_and_code(rule_file, test_files)
        
        if dataset_item is None:
            logging.warning(f"Не удалось обработать правило: {rule_file}")
            skipped_count += 1
            continue
        
        # Сохраняем в выходную директорию, сохраняя структуру папок
        relative_path = rule_file.relative_to(repo_path)
        output_path = output_dir / relative_path.with_suffix('.json')
        
        # Создаем поддиректории если нужно
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем датасет
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset_item, f, ensure_ascii=False, indent=2)
        
        processed_count += 1
    
    print(f"Обработка завершена:")
    print(f"  Успешно обработано: {processed_count} правил")
    print(f"  Пропущено: {skipped_count} правил")
    print(f"  Логи сохранены в: missing_rules.log")

if __name__ == "__main__":
    # Укажите путь к репозиторию semgrep-rules и выходной директории
    repo_path = "semgrep-rules"  # Замените на актуальный путь
    output_dir = "semgrep_dataset"
    
    process_semgrep_repository(repo_path, output_dir)