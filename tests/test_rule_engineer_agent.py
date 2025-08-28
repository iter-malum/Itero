#!/usr/bin/env python3
"""
Тестирование Rule Engineer Agent.
"""

import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.rule_engineer_agent import RuleEngineerAgent
from config.llm_config import LLM_CONFIG

def test_rule_engineer_agent():
    """Тестирование Rule Engineer Agent."""
    print("Инициализация RuleEngineerAgent...")
    rule_engineer = RuleEngineerAgent(LLM_CONFIG)
    
    # Тестовые примеры
    test_cases = [
        {
            "description": "SQL-инъекция через конкатенацию строк в Python",
            "code": """query = "SELECT * FROM users WHERE username = '" + username + "'"""
        },
        {
            "description": "Использование устаревшей функции хеширования MD5",
            "code": """import hashlib\nhash = hashlib.md5(password.encode()).hexdigest()"""
        },
        {
            "description": "Потенциальная XSS-уязвимость через innerHTML в JavaScript",
            "code": """document.getElementById("content").innerHTML = userInput;"""
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n{'='*60}")
        print(f"ТЕСТ {i+1}: {test_case['description']}")
        print(f"{'='*60}")
        
        result = rule_engineer.create_or_update_rule(
            problem_description=test_case['description'],
            code_example=test_case['code']
        )
        
        if result['success']:
            print("✓ Правило успешно создано!")
            print("\nСодержимое правила:")
            print(result['rule_yaml'])
            
            # Сохраняем правило в файл
            filename = f"test_rule_{i+1}.yaml"
            filepath = rule_engineer.save_rule_to_file(result['rule_yaml'], filename)
            print(f"\nПравило сохранено в: {filepath}")
        else:
            print("✗ Ошибка при создании правила:")
            print(result['message'])

def test_rule_update():
    """Тестирование обновления существующего правила."""
    print("\n\n" + "="*60)
    print("ТЕСТ ОБНОВЛЕНИЯ ПРАВИЛА")
    print("="*60)
    
    rule_engineer = RuleEngineerAgent(LLM_CONFIG)
    
    # Пример похожего правила (имитация результата поиска)
    similar_rules = [
        {
            "id": "hardcoded-password",
            "message": "Обнаружен жестко закодированный пароль",
            "source_file": "security_rules.yaml"
        }
    ]
    
    result = rule_engineer.create_or_update_rule(
        problem_description="Обнаружение жестко закодированного секретного ключа в Python коде",
        code_example="""api_key = 'sk_1234567890abcdef'""",
        similar_rules=similar_rules
    )
    
    if result['success']:
        print("✓ Правило успешно обновлено!")
        print("\nСодержимое правила:")
        print(result['rule_yaml'])
        print(f"Это новое правило: {result['is_new']}")
    else:
        print("✗ Ошибка при обновлении правила:")
        print(result['message'])

if __name__ == "__main__":
    test_rule_engineer_agent()
    test_rule_update()