#!/usr/bin/env python3
"""
УЛУЧШЕННЫЙ скрипт для преобразования правил Semgrep в формат JSONL для обучения.
Теперь с поддержкой различных форматов аннотаций и лучшим поиском тестовых файлов.
"""
import yaml
import json
from pathlib import Path
import logging
import re

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
RAW_DATA_DIR = Path("../data/raw/semgrep-rules")
PROCESSED_DATA_DIR = Path("../data/processed")
SAMPLE_OUTPUT_DIR = Path("../data/samples")

# Расширенные расширения файлов для разных языков
LANGUAGE_EXTENSIONS = {
    'csharp': ['.cs'],
    'python': ['.py'],
    'javascript': ['.js', '.ts', '.jsx', '.tsx'],
    'java': ['.java'],
    'go': ['.go'],
    'ruby': ['.rb'],
    'php': ['.php'],
    'hcl': ['.tf'],
    'rust': ['.rs'],
    'c': ['.c', '.h'],
    'cpp': ['.cpp', '.cc', '.cxx', '.h', '.hpp'],
    'html': ['.html', '.htm'],
    'json': ['.json'],
    'yaml': ['.yaml', '.yml'],
    'generic': ['.txt', '']
}

# Расширенные паттерны для поиска аннотаций
ANNOTATION_PATTERNS = [
    # Стандартные форматы
    r'(?:#|\/\/|<!--|;)\s*(ruleid|ok):\s*([\w\-\.]+)',
    r'(?:#|\/\/|<!--|;)\s*(ruleid|ok)\s*=\s*([\w\-\.]+)',
    # С комментариями после
    r'(?:#|\/\/|<!--|;)\s*(ruleid|ok):\s*([\w\-\.]+)\s*(?:#.*)?$',
    # В формате TODО
    r'TODO\s*(ruleid|ok):\s*([\w\-\.]+)',
]

def parse_rule_file(rule_path):
    """Парсит YAML-файл правила и извлекает информацию"""
    try:
        with open(rule_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Пропускаем тестовые файлы (содержат .test. в имени)
        if '.test.' in rule_path.name or '.fixed.' in rule_path.name:
            return None
            
        rule_data = yaml.safe_load(content)
            
        if not rule_data or 'rules' not in rule_data:
            return None
            
        rule = rule_data['rules'][0]
        rule_info = {
            'id': rule.get('id', ''),
            'message': rule.get('message', ''),
            'languages': rule.get('languages', []),
            'severity': rule.get('severity', ''),
            'patterns': rule.get('patterns', []),
            'pattern': rule.get('pattern', ''),
            'pattern-either': rule.get('pattern-either', []),
            'pattern-regex': rule.get('pattern-regex', ''),
            'metavariable-regex': rule.get('metavariable-regex', {}),
            'pattern-inside': rule.get('pattern-inside', ''),
            'pattern-not': rule.get('pattern-not', ''),
            'metadata': rule.get('metadata', {}),
            'file_path': str(rule_path.relative_to(RAW_DATA_DIR))
        }
        
        return rule_info
        
    except yaml.YAMLError as e:
        logger.debug(f"YAML ошибка в {rule_path}: {str(e)}")
        return None
    except Exception as e:
        logger.debug(f"Ошибка при парсинге {rule_path}: {str(e)}")
        return None

def find_test_files(rule_path, languages):
    """Ищет тестовые файлы для правила - РАСШИРЕННАЯ ВЕРСИЯ"""
    rule_dir = rule_path.parent
    rule_stem = rule_path.stem
    test_files = []
    
    # Убираем суффиксы типа .fixed, .test из имени правила
    clean_stem = rule_stem.replace('.fixed', '').replace('.test', '')
    
    # Проверяем возможные расширения для языка
    for lang in languages:
        if lang in LANGUAGE_EXTENSIONS:
            for ext in LANGUAGE_EXTENSIONS[lang]:
                # 1. Проверяем файл с тем же именем
                test_file = rule_dir / f"{clean_stem}{ext}"
                if test_file.exists() and test_file != rule_path:
                    test_files.append(test_file)
                
                # 2. Проверяем в поддиректории tests
                test_dir_file = rule_dir / "tests" / f"{clean_stem}{ext}"
                if test_dir_file.exists():
                    test_files.append(test_dir_file)
                    
                # 3. Проверяем файлы с test в имени
                for possible_file in rule_dir.glob(f"*test*{ext}"):
                    if possible_file != rule_path and clean_stem in possible_file.stem:
                        test_files.append(possible_file)
                
                # 4. Проверяем любые файлы с подходящим расширением в tests
                test_dir = rule_dir / "tests"
                if test_dir.exists():
                    for test_file in test_dir.glob(f"*{ext}"):
                        if test_file not in test_files:
                            test_files.append(test_file)
    
    return test_files

def extract_annotated_code_improved(test_file_content, rule_id):
    """Извлекает код с аннотациями - РАСШИРЕННАЯ ВЕРСИЯ"""
    sections = {
        'bad': [],  # ruleid
        'good': []  # ok
    }
    
    # Ищем все аннотации в файле
    annotations = []
    lines = test_file_content.split('\n')
    
    for line_num, line in enumerate(lines):
        for pattern in ANNOTATION_PATTERNS:
            matches = re.findall(pattern, line, re.IGNORECASE)
            for match_type, match_id in matches:
                if match_id == rule_id or match_id == 'ALL' or rule_id in match_id:
                    annotations.append({
                        'type': match_type,
                        'line': line_num,
                        'content': line
                    })
    
    if not annotations:
        return sections
    
    # Группируем код по аннотациям
    for i, annotation in enumerate(annotations):
        start_line = annotation['line']
        
        # Определяем конец блока кода
        if i < len(annotations) - 1:
            end_line = annotations[i + 1]['line']
        else:
            end_line = len(lines)
        
        # Извлекаем код между аннотацией и следующей аннотацией
        code_block = '\n'.join(lines[start_line:end_line])
        
        if annotation['type'] == 'ruleid':
            sections['bad'].append(code_block)
        elif annotation['type'] == 'ok':
            sections['good'].append(code_block)
    
    return sections

def create_training_examples_improved(rule_info, test_files):
    """Создает примеры для обучения - РАСШИРЕННАЯ ВЕРСИЯ"""
    examples = []
    
    for test_file in test_files:
        try:
            with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
                test_content = f.read()
                
            # Извлекаем код с аннотациями
            annotated_sections = extract_annotated_code_improved(test_content, rule_info['id'])
            
            if not annotated_sections['bad']:
                continue
                
            # Создаем промпт и completion для каждого плохого примера
            for bad_code in annotated_sections['bad']:
                # Формируем промпт
                language = rule_info['languages'][0] if rule_info['languages'] else 'generic'
                
                prompt_parts = [
                    f"На языке {', '.join(rule_info['languages'])} найди проблему: {rule_info['message']}",
                    f"Уязвимый код:",
                    f"```{language}",
                    bad_code,
                    "```"
                ]
                
                # Добавляем хорошие примеры, если есть
                if annotated_sections['good']:
                    prompt_parts.append("Безопасный код:")
                    for good_code in annotated_sections['good'][:2]:  # Ограничиваем количество
                        prompt_parts.extend([
                            f"```{language}",
                            good_code,
                            "```"
                        ])
                
                prompt = '\n'.join(prompt_parts)
                
                # Формируем правило Semgrep
                rule_yaml = {
                    "rules": [
                        {
                            "id": rule_info["id"],
                            "message": rule_info["message"],
                            "languages": rule_info["languages"],
                            "severity": rule_info["severity"],
                        }
                    ]
                }
                
                # Добавляем паттерны
                for pattern_type in ['pattern', 'patterns', 'pattern-either', 'pattern-regex', 
                                   'metavariable-regex', 'pattern-inside', 'pattern-not']:
                    if rule_info.get(pattern_type):
                        rule_yaml["rules"][0][pattern_type] = rule_info[pattern_type]
                        
                completion = f"""```yaml
{yaml.dump(rule_yaml, default_flow_style=False, allow_unicode=True, width=1000)}```"""
                
                examples.append({
                    "prompt": prompt,
                    "completion": completion
                })
                
        except Exception as e:
            logger.debug(f"Ошибка при обработке тестового файла {test_file}: {str(e)}")
            continue
            
    return examples

def process_rules_improved():
    """Основная функция обработки правил - УЛУЧШЕННАЯ ВЕРСИЯ"""
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    output_file = PROCESSED_DATA_DIR / "semgrep_training_data.jsonl"
    stats = {
        "total_rules": 0, 
        "processed_rules": 0, 
        "examples": 0, 
        "no_test_files": 0, 
        "no_annotations": 0,
        "skipped_test_files": 0
    }
    
    # Собираем все YAML-файлы, исключая тестовые
    yaml_files = [
        f for f in RAW_DATA_DIR.rglob("*.yaml") 
        if '.test.' not in f.name and '.fixed.' not in f.name
    ]
    stats["total_rules"] = len(yaml_files)
    
    logger.info(f"Найдено {stats['total_rules']} YAML-файлов для обработки (исключая тестовые)")
    
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for i, yaml_file in enumerate(yaml_files):
            if i % 100 == 0:
                logger.info(f"Обработано {i}/{stats['total_rules']} файлов")
                
            # Парсим правило
            rule_info = parse_rule_file(yaml_file)
            if not rule_info or not rule_info.get('languages'):
                continue
                
            # Ищем тестовые файлы
            test_files = find_test_files(yaml_file, rule_info['languages'])
            if not test_files:
                stats["no_test_files"] += 1
                continue
                
            # Создаем примеры для обучения
            examples = create_training_examples_improved(rule_info, test_files)
            if not examples:
                stats["no_annotations"] += 1
                continue
                
            # Записываем в файл
            for example in examples:
                json_line = json.dumps(example, ensure_ascii=False)
                out_f.write(json_line + '\n')
                stats["examples"] += 1
                
            stats["processed_rules"] += 1
            
            # Сохраняем несколько примеров для визуальной проверки
            if stats["processed_rules"] <= 5:
                sample_file = SAMPLE_OUTPUT_DIR / f"sample_{stats['processed_rules']}.txt"
                with open(sample_file, 'w', encoding='utf-8') as sample_f:
                    sample_f.write(f"=== Правило: {rule_info['id']} ===\n")
                    sample_f.write("=== PROMPT ===\n")
                    sample_f.write(examples[0]["prompt"][:500] + "...\n")
                    sample_f.write("\n\n=== COMPLETION ===\n")
                    sample_f.write(examples[0]["completion"][:500] + "...\n")
                    sample_f.write("\n" + "="*50 + "\n")
    
    # Сохраняем статистику
    stats_file = PROCESSED_DATA_DIR / "processing_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
        
    logger.info(f"Обработка завершена. Создано {stats['examples']} примеров из {stats['processed_rules']} правил")
    logger.info(f"Правил без тестовых файлов: {stats['no_test_files']}")
    logger.info(f"Правил без аннотаций: {stats['no_annotations']}")
    
    return stats

if __name__ == "__main__":
    logger.info("=== Начало обработки правил (УЛУЧШЕННАЯ ВЕРСИЯ) ===")
    stats = process_rules_improved()
    logger.info("=== Обработка завершена ===")