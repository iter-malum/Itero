#!/usr/bin/env python3
"""
Скрипт для обновления правил из официального репозитория Semgrep.
Запуск: python scripts/update_rules.py
"""

import os
import subprocess
import shutil
from utils.vector_db_manager import VectorDBManager

def update_rules():
    """Обновляет правила из официального репозитория Semgrep."""
    print("Обновление правил из официального репозитория...")
    
    # Пути к директориям
    official_dir = "./data/official_rules"
    raw_dir = "./data/raw_rules"
    backup_dir = "./data/backup_rules"
    
    # Создаем backup текущих правил
    if os.path.exists(raw_dir):
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        shutil.copytree(raw_dir, backup_dir)
        print(f"Создан backup правил в {backup_dir}")
    
    # Обновляем репозиторий
    if os.path.exists(official_dir):
        os.chdir(official_dir)
        result = subprocess.run(["git", "pull"], capture_output=True, text=True)
        if result.returncode == 0:
            print("Реpository успешно обновлен")
        else:
            print(f"Ошибка при обновлении репозитория: {result.stderr}")
        os.chdir("../..")
    else:
        # Клонируем репозиторий если его нет
        result = subprocess.run([
            "git", "clone", 
            "https://github.com/semgrep/semgrep-rules.git", 
            official_dir
        ], capture_output=True, text=True)
        if result.returncode == 0:
            print("Реpository успешно клонирован")
        else:
            print(f"Ошибка при клонировании репозитория: {result.stderr}")
            return False
    
    # Копируем правила в рабочую директорию
    if os.path.exists(raw_dir):
        shutil.rmtree(raw_dir)
    shutil.copytree(official_dir, raw_dir)
    
    # Удаляем служебные файлы git
    git_dir = os.path.join(raw_dir, ".git")
    if os.path.exists(git_dir):
        shutil.rmtree(git_dir)
    
    # Удаляем README и другие ненужные файлы
    for file in ["README.md", "LICENSE", ".gitignore"]:
        file_path = os.path.join(raw_dir, file)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    print("Правила успешно обновлены")
    
    # Перестраиваем векторную БД
    print("Перестроение векторной БД...")
    db_manager = VectorDBManager()
    db_manager.build_vector_db(raw_dir)
    
    return True

if __name__ == "__main__":
    update_rules()