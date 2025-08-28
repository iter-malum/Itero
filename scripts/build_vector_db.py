#!/usr/bin/env python3
"""
Скрипт для построения векторной базы данных из правил Semgrep.
Запуск: python scripts/build_vector_db.py
"""

import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.vector_db_manager import build_vector_db_from_rules

if __name__ == "__main__":
    print("Начинаем построение векторной базы данных правил Semgrep...")
    build_vector_db_from_rules()
    print("Векторная БД успешно построена!")