#!/usr/bin/env python3
"""
Скрипт для построения векторной базы данных из правил Semgrep.
Теперь поддерживает структуру официального репозитория.
"""

import sys
import os
import yaml

# Добавляем корневую директорию проекта в путь Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.vector_db_manager import VectorDBManager

def build_vector_db_from_rules(rules_dir: str = "./data/raw_rules"):
    """
    Утилитарная функция для быстрого построения векторной БД из правил.
    Теперь рекурсивно обрабатывает поддиректории.
    
    Args:
        rules_dir (str): Путь к директории с правилами Semgrep
    """
    db_manager = VectorDBManager()
    
    # Сканируем все поддиректории рекурсивно
    yaml_files = []
    for root, dirs, files in os.walk(rules_dir):
        for file in files:
            if file.endswith(('.yaml', '.yml')):
                yaml_files.append(os.path.join(root, file))
    
    print(f"Найдено {len(yaml_files)} YAML-файлов в {rules_dir}")
    db_manager.build_vector_db(rules_dir)

if __name__ == "__main__":
    print("Начинаем построение векторной базы данных правил Semgrep...")
    build_vector_db_from_rules()
    print("Векторная БД успешно построена!")