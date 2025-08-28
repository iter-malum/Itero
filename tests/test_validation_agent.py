#!/usr/bin/env python3
"""
Тестирование Validation Agent.
"""

import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.validation_agent import ValidationAgent
from config.llm_config import LLM_CONFIG

def test_validation_agent():
    """Тестирование Validation Agent."""
    print("Инициализация ValidationAgent...")
    validation_agent = ValidationAgent(LLM_CONFIG)
    
    # Пример правильного правила для SQL injection
    good_rule_yaml = """
rules:
- id: sql-injection-concat
  message: "Potential SQL injection through string concatenation"
  languages: [python]
  severity: ERROR
  patterns:
  - pattern: |
      $QUERY = "SELECT ... " + $USER_INPUT + " ..."
  - metavariable-regex:
      metavariable: $USER_INPUT
      regex: .*
"""

    # Пример неправильного правила (с синтаксической ошибкой)
    bad_rule_yaml = """
rules:
- id: bad-rule
  message: "This rule has syntax error"
  languages: [python]
  severity: ERROR
  pattern: |
    broken pattern without proper closure
"""

    # Тестовые примеры кода
    positive_test = '''
query = "SELECT * FROM users WHERE username = '" + username + "'"
result = cursor.execute(query)
'''

    negative_test = '''
query = "SELECT * FROM users WHERE status = 'active'"
result = cursor.execute(query)
'''

    print("=" * 60)
    print("ТЕСТ 1: Валидация хорошего правила")
    print("=" * 60)
    
    result = validation_agent.validate_rule(
        rule_yaml=good_rule_yaml,
        positive_test=positive_test,
        negative_test=negative_test,
        rule_id="sql-injection-concat"
    )
    
    if result["success"]:
        print("✓ Валидация завершена успешно!")
        print("\nАнализ LLM:")
        print(result["llm_analysis"])
        
        print("\nАвтоматическая валидация:")
        print(f"Пройдена: {result['validation_passed']}")
        print(f"Позитивный тест: {result['auto_validation']['positive_test']['success']}")
        print(f"Негативный тест: {result['auto_validation']['negative_test']['success']}")
    else:
        print("✗ Ошибка при валидации:")
        print(result.get("error", "Неизвестная ошибка"))
    
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Валидация плохого правила")
    print("=" * 60)
    
    result = validation_agent.validate_rule(
        rule_yaml=bad_rule_yaml,
        positive_test=positive_test,
        negative_test=negative_test,
        rule_id="bad-rule"
    )
    
    if result["success"]:
        print("✓ Валидация завершена (ожидаем失败)!")
        print("\nАнализ LLM:")
        print(result["llm_analysis"])
        
        print("\nАвтоматическая валидация:")
        print(f"Пройдена: {result['validation_passed']}")
    else:
        print("✗ Ошибка при валидации (ожидаемо для плохого правила):")
        print(result.get("error", "Неизвестная ошибка"))

if __name__ == "__main__":
    test_validation_agent()