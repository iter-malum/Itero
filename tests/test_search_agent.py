#!/usr/bin/env python3
"""
Тестирование Search Agent.
"""

import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.vector_db_manager import VectorDBManager
from agents.search_agent import SearchAgent
from config.llm_config import LLM_CONFIG

def test_search_agent():
    """Тестирование Search Agent."""
    print("Инициализация VectorDBManager...")
    vector_db_manager = VectorDBManager()
    
    print("Инициализация SearchAgent...")
    search_agent = SearchAgent(LLM_CONFIG, vector_db_manager)
    
    # Тестовые примеры
    test_cases = [
        "В коде есть SQL-инъекция через конкатенацию строк",
        "Используется слабый алгоритм хеширования MD5",
        "Возможность XSS через innerHTML",
        "В коде жестко закодирован секретный ключ",
        "Небезопасная десериализация данных"
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n{'='*50}")
        print(f"ТЕСТ {i+1}: {test_case}")
        print(f"{'='*50}")
        
        result = search_agent.find_relevant_rules(test_case)
        print(result)

if __name__ == "__main__":
    test_search_agent()