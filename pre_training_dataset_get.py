import json
import os
import glob
import random
from pathlib import Path
import yaml
from collections import defaultdict
from datetime import datetime

def safe_instruction_format(instruction_template, description):
    """
    Безопасное форматирование строки с обработкой ошибок
    """
    try:
        # Если в описании уже есть форматирование, используем его как есть
        if '{' in instruction_template and '}' in instruction_template:
            return instruction_template.format(desc=description)
        else:
            return instruction_template.replace('{desc}', description)
    except:
        # Если возникает ошибка форматирования, возвращаем оригинальную инструкцию
        return description

def enhance_instruction_variety(original_instruction, rule_type):
    """
    Создает разнообразные инструкции для лучшего обобщения
    """
    variations = {
        'create': [
            "Напиши правило Semgrep для: {desc}",
            "Создай правило Semgrep для обнаружения: {desc}",
            "Разработай правило Semgrep для выявления: {desc}",
            "Сгенерируй правило Semgrep для поиска: {desc}",
            "Составь правило Semgrep для: {desc}",
            "Напиши Semgrep правило для обнаружения: {desc}",
            "Создай Semgrep правило для: {desc}"
        ],
        'modify': [
            "Доработай существующее правило Semgrep: {desc}",
            "Улучши правило Semgrep для: {desc}", 
            "Модифицируй правило Semgrep для лучшего обнаружения: {desc}",
            "Обнови правило Semgrep для: {desc}"
        ]
    }
    
    # Определяем тип задачи по инструкции
    task_type = 'modify' if any(word in original_instruction.lower() for word in 
                               ['доработай', 'модифицируй', 'обнови', 'улучши']) else 'create'
    
    # Берем 2 случайные вариации + оригинал
    selected_variations = random.sample(variations[task_type], 2) + [original_instruction]
    
    # Безопасно применяем форматирование
    formatted_instructions = []
    for variation in selected_variations:
        # Извлекаем чистое описание из оригинальной инструкции
        clean_description = original_instruction
        for prefix in ["Создай правило Semgrep для обнаружения ", "Напиши правило Semgrep для "]:
            if original_instruction.startswith(prefix):
                clean_description = original_instruction[len(prefix):]
                break
        
        formatted_instruction = safe_instruction_format(variation, clean_description)
        formatted_instructions.append(formatted_instruction)
    
    return formatted_instructions

def validate_semgrep_yaml(yaml_text):
    """
    Проверяет валидность сгенерированного YAML с улучшенной обработкой ошибок
    """
    try:
        # Пытаемся распарсить YAML
        data = yaml.safe_load(yaml_text)
        
        # Проверяем обязательные поля
        if not data or 'rules' not in data:
            return False
            
        rule = data['rules'][0] if isinstance(data['rules'], list) and len(data['rules']) > 0 else data.get('rules', {})
        required_fields = ['id', 'message', 'languages', 'severity']
        
        return all(field in rule for field in required_fields)
        
    except Exception as e:
        print(f"    YAML validation error: {str(e)}")
        return False

def safe_get_examples(examples_list, max_examples=3):
    """
    Безопасно извлекает примеры кода с ограничением длины
    """
    if not examples_list:
        return []
    
    safe_examples = []
    for example in examples_list[:max_examples]:
        if example and len(str(example)) < 1000:  # Ограничиваем слишком длинные примеры
            safe_examples.append(str(example))
    
    return safe_examples

def create_learning_example(data, instruction_variation):
    """
    Создает один пример для обучения с улучшенным форматом и обработкой ошибок
    """
    try:
        code_context = data.get("code_context", {})
        metadata = data.get("metadata", {})
        
        # Безопасно извлекаем примеры кода
        dangerous_examples = safe_get_examples(code_context.get("dangerous_examples", []))
        safe_examples = safe_get_examples(code_context.get("safe_examples", []))
        
        # Формируем расширенный контекст
        input_context = f"""Требования:
- Язык: {data.get("language", metadata.get("language", ""))}
- Тип анализа: {metadata.get("mode", "")}
- CWE: {data.get("CWE", metadata.get("cwe", ""))}
- Серьезность: {metadata.get("severity", "")}

Контекст кода:
{code_context.get("full_code", "")[:2000]}  # Ограничиваем длину

Опасные паттерны:
{chr(10).join(f"• {example}" for example in dangerous_examples)}

Безопасные паттерны:  
{chr(10).join(f"• {example}" for example in safe_examples)}"""

        # Добавляем легенду аннотаций если она есть
        annotation_legend = code_context.get("annotation_legend", {})
        if annotation_legend:
            input_context += f"\n\nЛегенда аннотаций:\n{chr(10).join(f'- {key}: {value}' for key, value in annotation_legend.items())}"
    
        # Формируем output с объяснением
        reasoning = data.get("reasoning", "")
        output = f"""{data["output"]}

# Логика правила:
{reasoning}

# Ключевые элементы:
- ID: {metadata.get("rule_id", "")}
- Язык: {metadata.get("language", "")} 
- Тип: {metadata.get("rule_type", "")}
- Серьезность: {metadata.get("severity", "")}"""
    
        return {
            "instruction": instruction_variation,
            "input": input_context,
            "output": output,
            "metadata": {
                "rule_id": metadata.get("rule_id", ""),
                "language": metadata.get("language", ""),
                "severity": metadata.get("severity", ""),
                "rule_type": metadata.get("rule_type", ""),
                "mode": metadata.get("mode", ""),
                "is_validation": False
            }
        }
    except Exception as e:
        print(f"    Error creating learning example: {str(e)}")
        return None

def transform_semgrep_data_enhanced(input_dir, output_file):
    """
    Улучшенная версия скрипта преобразования данных с обработкой ошибок
    """
    all_examples = []
    
    # Собираем все JSON файлы
    json_files = glob.glob(os.path.join(input_dir, "**", "*.json"), recursive=True)
    
    print(f"Найдено JSON файлов: {len(json_files)}")
    
    language_stats = {}
    error_files = []
    
    for i, file_path in enumerate(json_files):
        if i % 100 == 0:
            print(f"Обработано {i}/{len(json_files)} файлов...")
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Валидируем исходное правило
            if not validate_semgrep_yaml(data.get("output", "")):
                print(f"⚠️  Пропущено невалидное правило: {file_path}")
                error_files.append(f"Invalid YAML: {file_path}")
                continue
            
            language = data.get("language", data.get("metadata", {}).get("language", "unknown"))
            language_stats[language] = language_stats.get(language, 0) + 1
            
            # Создаем вариации инструкций
            instruction_variations = enhance_instruction_variety(
                data.get("instruction", ""), 
                data.get("metadata", {}).get("rule_type", "create")
            )
            
            # Создаем примеры для каждой вариации
            for instruction_var in instruction_variations:
                example = create_learning_example(data, instruction_var)
                if example is not None:
                    all_examples.append(example)
                
        except Exception as e:
            error_msg = f"❌ Ошибка обработки {file_path}: {str(e)}"
            print(error_msg)
            error_files.append(error_msg)
            continue
    
    print(f"\n📊 Статистика по языкам:")
    for lang, count in sorted(language_stats.items()):
        print(f"   {lang}: {count} файлов")
    
    print(f"🎯 Всего примеров после аугментации: {len(all_examples)}")
    
    if error_files:
        print(f"🚨 Файлов с ошибками: {len(error_files)}")
        # Сохраняем логи ошибок
        with open(output_file.replace('.json', '_errors.log'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(error_files))
    
    # Сохраняем полный датасет
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_examples, f, ensure_ascii=False, indent=2)
    
    return all_examples

def create_stratified_split(all_examples, val_ratio=0.1):
    """
    Стратифицированное разделение по языкам и типам правил
    """
    # Группируем примеры по языку и типу правила
    groups = defaultdict(list)
    
    for example in all_examples:
        key = (example["metadata"]["language"], example["metadata"].get("rule_type", "audit"))
        groups[key].append(example)
    
    train_data = []
    val_data = []
    
    # Для каждой группы разделяем пропорционально
    for group_key, examples in groups.items():
        random.shuffle(examples)
        
        split_index = int(len(examples) * (1 - val_ratio))
        train_data.extend(examples[:split_index])
        val_data.extend(examples[split_index:])
        
        # Помечаем валидационные примеры
        for example in val_data:
            example["metadata"]["is_validation"] = True
    
    # Перемешиваем итоговые наборы
    random.shuffle(train_data)
    random.shuffle(val_data)
    
    return train_data, val_data

def analyze_final_datasets(train_data, val_data):
    """
    Анализ итоговых наборов данных
    """
    print("\n📈 АНАЛИЗ ДАТАСЕТОВ:")
    print(f"   Обучающая выборка: {len(train_data)} примеров")
    print(f"   Валидационная выборка: {len(val_data)} примеров")
    total = len(train_data) + len(val_data)
    if total > 0:
        print(f"   Соотношение: {len(train_data)/total*100:.1f}% / {len(val_data)/total*100:.1f}%")
    
    # Статистика по языкам
    train_langs = defaultdict(int)
    val_langs = defaultdict(int)
    
    for example in train_data:
        train_langs[example["metadata"]["language"]] += 1
    for example in val_data:
        val_langs[example["metadata"]["language"]] += 1
    
    print("\n🌍 Распределение по языкам:")
    all_langs = set(train_langs.keys()) | set(val_langs.keys())
    for lang in sorted(all_langs):
        train_count = train_langs.get(lang, 0)
        val_count = val_langs.get(lang, 0)
        total = train_count + val_count
        if total > 0:
            print(f"   {lang}: {train_count} train, {val_count} val ({val_count/total*100:.1f}% val)")

def clean_duplicate_prefixes(instructions):
    """
    Очищает инструкции от дублирующихся префиксов
    """
    cleaned = []
    for instruction in instructions:
        # Убираем дублирование типа "Разработай правило Semgrep для выявления: Создай правило Semgrep для обнаружения"
        if "Создай правило Semgrep для обнаружения" in instruction and "Разработай правило Semgrep для выявления" in instruction:
            # Оставляем только одну часть
            instruction = instruction.split("Разработай правило Semgrep для выявления: ")[-1]
        cleaned.append(instruction)
    return cleaned

if __name__ == "__main__":
    # Конфигурация
    INPUT_DIRECTORY = "semgrep_dataset_train"
    OUTPUT_DIR = "semgrep_prepared_data"
    
    # Создаем директорию для результатов
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Преобразуем и аугментируем данные
    print("🔄 Преобразование данных...")
    all_examples = transform_semgrep_data_enhanced(
        INPUT_DIRECTORY, 
        os.path.join(OUTPUT_DIR, "semgrep_full_dataset.json")
    )
    
    # 2. Очищаем инструкции от дублирующихся префиксов
    print("\n🧹 Очистка инструкций...")
    for example in all_examples:
        example["instruction"] = clean_duplicate_prefixes([example["instruction"]])[0]
    
    # 3. Разделяем на train/validation
    print("\n✂️  Разделение на train/validation...")
    train_data, val_data = create_stratified_split(all_examples, val_ratio=0.1)
    
    # 4. Сохраняем разделенные данные
    with open(os.path.join(OUTPUT_DIR, "train_data.json"), 'w', encoding='utf-8') as f:
        json.dump(train_data, f, ensure_ascii=False, indent=2)
    
    with open(os.path.join(OUTPUT_DIR, "val_data.json"), 'w', encoding='utf-8') as f:
        json.dump(val_data, f, ensure_ascii=False, indent=2)
    
    # 5. Анализируем результаты
    analyze_final_datasets(train_data, val_data)
    
    # 6. Создаем конфиг для обучения
    config = {
        "dataset_info": {
            "total_examples": len(all_examples),
            "train_examples": len(train_data),
            "val_examples": len(val_data),
            "languages": list(set(ex["metadata"]["language"] for ex in all_examples)),
            "created_at": str(datetime.now())
        },
        "training_notes": "Стратифицированное разделение по языкам и типам правил"
    }
    
    with open(os.path.join(OUTPUT_DIR, "dataset_config.json"), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Все файлы сохранены в директории: {OUTPUT_DIR}")