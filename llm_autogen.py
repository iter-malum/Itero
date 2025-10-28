import json
import os
import time
import logging
import sys
import re
from pathlib import Path
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enrich_dataset.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Конфигурация GigaChat
GIGACHAT_CREDENTIALS = "MDE5YTI1OGUtMGY1OS03YzgxLTlmZDUtY2FjNjBhMGQ1OGY0OmExMTU3ODE0LTRmYzktNDJkNC1iMzRmLTdlOTdmMjJiZDhlYQ=="
SCOPE = "GIGACHAT_API_PERS"

def initialize_gigachat():
    """
    Инициализирует и возвращает клиент GigaChat
    """
    try:
        logging.info("Инициализация GigaChat клиента...")
        
        giga = GigaChat(
            credentials=GIGACHAT_CREDENTIALS,
            scope=SCOPE,
            model="GigaChat",
            verify_ssl_certs=False,
            timeout=60
        )
        
        # Тестируем подключение
        models = giga.get_models()
        logging.info(f"✅ Подключение к API успешно. Доступно моделей: {len(models.data)}")
        
        return giga
        
    except Exception as e:
        logging.error(f"❌ Ошибка при инициализации GigaChat: {str(e)}")
        return None

def get_llm_response(giga, instruction, full_code, rule_yaml):
    """
    Получает ответ от LLM для обогащения датасета
    """
    system_prompt = """Ты - эксперт по безопасности и статическому анализу кода с помощью Semgrep. 
Проанализируй предоставленное правило Semgrep и соответствующий код. На основе твоего ответа будет дообучаться LLM модель, поэтому дай ей максимально нужный контекст по написанию текущего правила, чтобы она смогла это понять и научиться писать правила самостоятельно.

ФОКУС НА ЛОГИКЕ ПРАВИЛА (reasoning должен содержать ТОЛЬКО):
- Тип анализа: search/taint и его параметры
- Структура паттернов: pattern/patterns/pattern-either/pattern-not и т.д
- Комбинация условий: логика И/ИЛИ/НЕ между паттернами
- Метапеременные: использование $VAR, $X и других
- Специальные операторы: pattern-inside, pattern-not-inside, ellipsis (...)
- Механизм сопоставления: как правило находит код


Верни ответ в формате JSON, без каких-либо дополнительных объяснений. СТРОГИЙ ФОРМАТ ОТВЕТА (ТОЛЬКО JSON):
{
  "reasoning": "техническое объяснение работы правила",
  "dangerous_examples": ["код1", "код2"],
  "safe_examples": ["код3", "код4"]
}
ПРАВИЛА:
1. reasoning: логике правила ограниченная 1000 символов
2. dangerous_examples: 2-3 примера опасного кода из предоставленных данных
3. safe_examples: 2-3 примера безопасного кода из предоставленных данных
4. НЕ экранируй кавычки в примерах
5. НЕ добавляй комментарии

Убедись, что JSON валиден и все строки правильно экранированы!"""

    user_prompt = f"""ИНСТРУКЦИЯ ДЛЯ СОЗДАНИЯ ПРАВИЛА:
{instruction}

ПОЛНЫЙ КОД ДЛЯ АНАЛИЗА:
{full_code}

YAML ПРАВИЛО SEMGREP:
{rule_yaml}

Сгенерируй reasoning, dangerous_examples и safe_examples на основе этой информации."""

    try:
        logging.info("Отправляем запрос к GigaChat...")
        
        # Создаем объект Chat с сообщениями
        messages = [
            Messages(role=MessagesRole.SYSTEM, content=system_prompt),
            Messages(role=MessagesRole.USER, content=user_prompt)
        ]
        
        chat = Chat(
            messages=messages,
            temperature=0.1,
            max_tokens=4096
        )
        
        response = giga.chat(chat)
        
        logging.info("✅ Успешно получили ответ от GigaChat")
        return response.choices[0].message.content
        
    except Exception as e:
        logging.error(f"❌ Ошибка при получении ответа от GigaChat: {str(e)}")
        return None

def robust_json_cleaner(json_str):
    """
    Мощный очиститель JSON, который исправляет самые распространенные ошибки
    """
    if not json_str:
        return None
        
    try:
        # 1. Удаляем управляющие символы
        json_str = re.sub(r'[\x00-\x1f\x7f]', '', json_str)
        
        # 2. Исправляем незавершенные массивы и объекты
        json_str = re.sub(r',\s*\]', ']', json_str)  # Лишние запятые перед ]
        json_str = re.sub(r',\s*\}', '}', json_str)  # Лишние запятые перед }
        
        # 3. Удаляем пустые элементы в массивах
        json_str = re.sub(r',\s*,', ',', json_str)  # Двойные запятые
        json_str = re.sub(r'\[\s*,', '[', json_str)  # Запятая после [
        json_str = re.sub(r',\s*\]', ']', json_str)  # Запятая перед ]
        
        # 4. Исправляем незавершенные строки в массивах
        lines = json_str.split('\n')
        cleaned_lines = []
        in_array = False
        array_depth = 0
        
        for line in lines:
            # Отслеживаем вхождение/выход из массивов
            array_depth += line.count('[') - line.count(']')
            
            if array_depth > 0:
                in_array = True
            else:
                in_array = False
                
            # Если в массиве и строка выглядит незавершенной, пропускаем её
            if in_array and re.search(r'^\s*\"[^\"]*$', line) and not re.search(r'\"\s*,?\s*$', line):
                continue
                
            cleaned_lines.append(line)
        
        json_str = '\n'.join(cleaned_lines)
        
        # 5. Экранируем кавычки внутри строк
        def escape_quotes(match):
            content = match.group(1)
            # Экранируем все двойные кавычки, кроме тех, что на границах строки
            content = content.replace('"', '\\"')
            return f'"{content}"'
        
        # Находим и исправляем строки в JSON
        json_str = re.sub(r'"([^"\\]*(\\.[^"\\]*)*)"', escape_quotes, json_str)
        
        # 6. Убеждаемся, что все массивы правильно закрыты
        open_braces = json_str.count('[')
        close_braces = json_str.count(']')
        if open_braces > close_braces:
            json_str += ']' * (open_braces - close_braces)
        
        open_curlies = json_str.count('{')
        close_curlies = json_str.count('}')
        if open_curlies > close_curlies:
            json_str += '}' * (open_curlies - close_curlies)
        
        return json_str
        
    except Exception as e:
        logging.warning(f"Ошибка при очистке JSON: {e}")
        return json_str

def extract_and_clean_json(text):
    """
    Извлекает и очищает JSON из текста ответа
    """
    if not text:
        return None
        
    text = text.strip()
    
    # Ищем JSON от первого { до последнего }
    start_idx = text.find('{')
    end_idx = text.rfind('}') + 1
    
    if start_idx == -1 or end_idx == 0:
        logging.error("Не найден JSON в ответе")
        return None
        
    json_str = text[start_idx:end_idx]
    
    # Применяем мощный очиститель
    cleaned_json = robust_json_cleaner(json_str)
    
    return cleaned_json


def aggressive_json_fix(json_str):
    """
    Агрессивное исправление JSON когда все остальные методы не помогают
    """
    try:
        # Если JSON начинается без кавычек, добавляем их ко всем ключам
        if not re.search(r'^\s*{', json_str):
            # Ищем паттерн ключей без кавычек и добавляем кавычки
            json_str = re.sub(r'(\w+)\s*:', r'"\1":', json_str)
        
        # Исправляем проблемы с запятыми в массивах
        json_str = re.sub(r',\s*,', ',', json_str)  # Двойные запятые
        json_str = re.sub(r',\s*\]', ']', json_str)  # Запятая перед ]
        json_str = re.sub(r'\[\s*,', '[', json_str)  # Запятая после [
        
        # Удаляем управляющие символы
        json_str = re.sub(r'[\x00-\x1f\x7f]', '', json_str)
        
        # Исправляем незакрытые кавычки в строках
        lines = json_str.split('\n')
        fixed_lines = []
        in_string = False
        
        for line in lines:
            fixed_line = ""
            for char in line:
                if char == '"':
                    in_string = not in_string
                    fixed_line += char
                elif char == ',' and not in_string:
                    fixed_line += char
                else:
                    fixed_line += char
            fixed_lines.append(fixed_line)
        
        return '\n'.join(fixed_lines)
        
    except Exception as e:
        logging.warning(f"Агрессивное исправление не удалось: {e}")
        return json_str
    
def ultra_safe_json_parse(json_str):
    """
    УЛЬТРА-надежный парсинг JSON с приоритетом на извлечение данных
    """
    if not json_str:
        return None
        
    # Базовый результат
    result = {
        "reasoning": "",
        "dangerous_examples": [],
        "safe_examples": []
    }
    
    # Попытка 1: Прямой парсинг
    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            if "reasoning" in data:
                result["reasoning"] = str(data["reasoning"])[:1000]  # Ограничиваем длину
            if "dangerous_examples" in data and isinstance(data["dangerous_examples"], list):
                result["dangerous_examples"] = [str(x)[:200] for x in data["dangerous_examples"][:3] if str(x).strip()]
            if "safe_examples" in data and isinstance(data["safe_examples"], list):
                result["safe_examples"] = [str(x)[:200] for x in data["safe_examples"][:3] if str(x).strip()]
            return result
    except:
        pass
    
    # Попытка 2: Ручное извлечение через regex (ПРИОРИТЕТНЫЙ МЕТОД)
    try:
        # Извлекаем reasoning (самое важное)
        reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]*)"', json_str)
        if not reasoning_match:
            reasoning_match = re.search(r'"reasoning"\s*:\s*\[([^\]]*)\]', json_str)
            if reasoning_match:
                # Если reasoning в массиве, объединяем
                items = re.findall(r'"([^"]*)"', reasoning_match.group(1))
                result["reasoning"] = " ".join(items)[:1000]
        else:
            result["reasoning"] = reasoning_match.group(1)[:1000]
        
        # Извлекаем dangerous_examples
        dangerous_match = re.search(r'"dangerous_examples"\s*:\s*\[([^\]]*)\]', json_str, re.DOTALL)
        if dangerous_match:
            examples = re.findall(r'"([^"]*)"', dangerous_match.group(1))
            result["dangerous_examples"] = [ex[:200] for ex in examples[:3] if ex.strip()]
        
        # Извлекаем safe_examples (ИСПРАВЛЕНА ОШИБКА - добавлена закрывающая скобка)
        safe_match = re.search(r'"safe_examples"\s*:\s*\[([^\]]*)\]', json_str, re.DOTALL)
        if safe_match:
            examples = re.findall(r'"([^"]*)"', safe_match.group(1))
            result["safe_examples"] = [ex[:200] for ex in examples[:3] if ex.strip()]  # Закрывающая скобка добавлена
        
        return result
        
    except Exception as e:
        logging.warning(f"Regex извлечение не удалось: {e}")
    
    # Попытка 3: Поиск любых массивов с примерами
    try:
        # Ищем любые массивы в JSON
        arrays = re.findall(r'(\[["\',\s\w\d\s\.\/\\\-\+\=\(\)]*\])', json_str)
        
        if len(arrays) >= 2:
            # Первый массив - dangerous, второй - safe
            dangerous_items = re.findall(r'"([^"]*)"', arrays[0])
            safe_items = re.findall(r'"([^"]*)"', arrays[1])
            
            result["dangerous_examples"] = [item[:200] for item in dangerous_items[:3] if item.strip()]
            result["safe_examples"] = [item[:200] for item in safe_items[:3] if item.strip()]
            
            # Ищем reasoning как текст перед первым массивом
            before_first_array = json_str.split(arrays[0])[0]
            reasoning_text = re.search(r'"reasoning"\s*:\s*"([^"]*)"', before_first_array)
            if reasoning_text:
                result["reasoning"] = reasoning_text.group(1)[:1000]
        
        return result
        
    except Exception as e:
        logging.warning(f"Поиск массивов не удался: {e}")
    
    return None

def parse_llm_response(llm_response):
    """
    УПРОЩЕННЫЙ парсинг ответа
    """
    try:
        logging.info("Упрощенный парсинг ответа от модели...")
        
        if not llm_response:
            logging.error("❌ Пустой ответ от модели")
            return None
        
        # Очищаем ответ - удаляем все кроме JSON
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if not json_match:
            logging.error("❌ JSON не найден в ответе")
            return None
            
        json_str = json_match.group(0)
        
        # Используем УЛЬТРА-надежный парсер
        parsed_data = ultra_safe_json_parse(json_str)
        
        if not parsed_data:
            logging.error("❌ Не удалось извлечь данные из JSON")
            return None
        
        # ПРОСТАЯ валидация
        if not parsed_data["reasoning"].strip():
            parsed_data["reasoning"] = "Объяснение не сгенерировано"
        
        if not parsed_data["dangerous_examples"]:
            parsed_data["dangerous_examples"] = ["Пример опасного кода не сгенерирован"]
            
        if not parsed_data["safe_examples"]:
            parsed_data["safe_examples"] = ["Пример безопасного кода не сгенерирован"]
        
        logging.info(f"✅ Извлечено: reasoning({len(parsed_data['reasoning'])}), "
                    f"dangerous({len(parsed_data['dangerous_examples'])}), "
                    f"safe({len(parsed_data['safe_examples'])})")
        
        return parsed_data
        
    except Exception as e:
        logging.error(f"❌ Ошибка при парсинге: {str(e)}")
        return None

def enrich_dataset_file(giga, file_path, output_dir, input_dir):
    """
    Обогащает файл с ПРИОРИТЕТОМ на успешное завершение
    """
    try:
        logging.info(f"📁 Обработка: {file_path.name}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            dataset_item = json.load(f)
        
        # Пропускаем уже обработанные
        if (dataset_item.get('reasoning') and 
            dataset_item['code_context'].get('dangerous_examples') and 
            dataset_item['code_context'].get('safe_examples')):
            logging.info(f"⏭️ Уже обработан: {file_path.name}")
            return True

        # Получаем ответ
        llm_response = get_llm_response(
            giga,
            dataset_item['instruction'],
            dataset_item['code_context']['full_code'],
            dataset_item['output']
        )

        if not llm_response:
            logging.error(f"❌ Нет ответа для: {file_path.name}")
            return False

        # Парсим ответ
        enriched_data = parse_llm_response(llm_response)
        
        if not enriched_data:
            logging.error(f"❌ Не распарсен ответ для: {file_path.name}")
            return False

        # ОБНОВЛЯЕМ ДАННЫЕ (даже если частичные)
        dataset_item['reasoning'] = enriched_data.get('reasoning', 'Объяснение не сгенерировано')
        dataset_item['code_context']['dangerous_examples'] = enriched_data.get('dangerous_examples', ['Пример не сгенерирован'])
        dataset_item['code_context']['safe_examples'] = enriched_data.get('safe_examples', ['Пример не сгенерирован'])

        # Сохраняем
        relative_path = file_path.relative_to(input_dir)
        output_path = Path(output_dir) / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset_item, f, ensure_ascii=False, indent=2)
        
        logging.info(f"✅ Успешно: {file_path.name}")
        return True

    except Exception as e:
        logging.error(f"❌ Критическая ошибка для {file_path.name}: {str(e)}")
        return False

def process_entire_dataset(input_dir, output_dir):
    """
    Обрабатывает весь датасет рекурсивно
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Создаем выходную директорию
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Инициализируем GigaChat
    giga = initialize_gigachat()
    if not giga:
        logging.error("Не удалось инициализировать GigaChat клиент. Проверьте ключ авторизации.")
        return
    
    processed = 0
    failed = 0
    
    # Рекурсивно ищем все JSON файлы
    json_files = list(input_path.rglob("*.json"))
    total_files = len(json_files)
    
    logging.info(f"📊 Найдено файлов для обработки: {total_files}")
    
    if total_files == 0:
        logging.error(f"❌ Не найдено JSON файлов в директории {input_dir}")
        return
    
    for i, file in enumerate(json_files):
        logging.info(f"🔄 Обработка файла {i+1}/{total_files}: {file}")
        
        if enrich_dataset_file(giga, file, output_dir, input_path):
            processed += 1
        else:
            failed += 1
        
        # Задержка чтобы не превысить лимиты API
        logging.info("⏳ Пауза 2 секунды перед следующим запросом...")
        time.sleep(2)
        
        # Каждые 10 файлов выводим прогресс
        if (i + 1) % 10 == 0:
            logging.info(f"📈 Прогресс: обработано {i + 1}/{total_files} файлов")
    
    logging.info(f"🎉 Обработка завершена! Успешно: {processed}, С ошибками: {failed}")

if __name__ == "__main__":
    # Настройки путей
    INPUT_DATASET_DIR = "semgrep_dataset"
    OUTPUT_DATASET_DIR = "semgrep_dataset_train"
    
    if not os.path.exists(INPUT_DATASET_DIR):
        logging.error(f"❌ Входная директория {INPUT_DATASET_DIR} не существует!")
        logging.info(f"📁 Текущая рабочая директория: {os.getcwd()}")
        exit(1)
    
    logging.info("🚀 Запуск обогащения датасета с использованием библиотеки GigaChat...")
    process_entire_dataset(INPUT_DATASET_DIR, OUTPUT_DATASET_DIR)