#!/usr/bin/env python3
"""
Тестирование полного workflow системы.
"""

import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import Orchestrator

def test_full_workflow():
    """Тестирование полного workflow."""
    print("Инициализация Orchestrator...")
    orchestrator = Orchestrator()
    
    # Тестовые примеры
    test_cases = [
        {
            "description": "SQL-инъекция через конкатенацию строк в Python",
            "code": """
query = "SELECT * FROM users WHERE username = '" + username + "'"
result = cursor.execute(query)
"""
        },
        {
            "description": "Использование устаревшей функции хеширования MD5",
            "code": """
import hashlib
hash = hashlib.md5(password.encode()).hexdigest()
"""
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n{'=' * 60}")
        print(f"ТЕСТ {i+1}: {test_case['description']}")
        print(f"{'=' * 60}")
        
        result = orchestrator.run_full_workflow(
            code_snippet=test_case["code"],
            vulnerability_description=test_case["description"]
        )
        
        if result["success"]:
            print("✓ Workflow завершен успешно!")
            print(f"Создание правила: {'Успех' if result['rule_creation_success'] else 'Неудача'}")
            print(f"Валидация: {'Пройдена' if result['validation_passed'] else 'Не пройдена'}")
            print(f"Тип: {'Новое правило' if result['is_new_rule'] else 'Обновление правила'}")
            
            if result["saved_path"]:
                print(f"Сохранено в: {result['saved_path']}")
        else:
            print("✗ Workflow завершен с ошибкой:")
            print(f"Этап: {result.get('step', 'unknown')}")
            print(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")

if __name__ == "__main__":
    test_full_workflow()