#!/usr/bin/env python3
"""
Скрипт для загрузки правил из репозитория semgrep-rules.
Сохраняет исходные YAML-файлы и соответствующие тесты.
"""
import os
import subprocess
import shutil
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
REPO_URL = "https://github.com/semgrep/semgrep-rules"
DATA_DIR = Path("../data/raw")
RULES_DIR = DATA_DIR / "semgrep-rules"

def clone_repository():
    """Клонирует репозиторий semgrep-rules"""
    if RULES_DIR.exists():
        logger.info(f"Репо уже существует в {RULES_DIR}, пропускаем клонирование")
        return True
        
    try:
        logger.info(f"Клонируем репозиторий {REPO_URL}")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(RULES_DIR)],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            logger.error(f"Ошибка при клонировании: {result.stderr}")
            return False
            
        logger.info("Репо успешно клонирован")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("Таймаут при клонировании репозитория")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}")
        return False

def get_repo_stats():
    """Собирает статистику по репозиторию"""
    if not RULES_DIR.exists():
        logger.error("Репо не существует, не могу собрать статистику")
        return
        
    yaml_files = list(RULES_DIR.rglob("*.yaml"))
    test_dirs = list(RULES_DIR.rglob("tests"))
    
    logger.info(f"Найдено YAML-файлов: {len(yaml_files)}")
    logger.info(f"Найдено тестовых директорий: {len(test_dirs)}")
    
    # Сохраняем статистику
    stats_file = DATA_DIR / "repo_stats.txt"
    with open(stats_file, 'w') as f:
        f.write(f"YAML файлов: {len(yaml_files)}\n")
        f.write(f"Тестовых директорий: {len(test_dirs)}\n")
    
    return len(yaml_files)

if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info("=== Начало загрузки данных ===")
    success = clone_repository()
    
    if success:
        rule_count = get_repo_stats()
        logger.info(f"=== Загрузка завершена. Правил найдено: {rule_count} ===")
    else:
        logger.error("=== Загрузка не удалась ===")