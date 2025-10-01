#!/usr/bin/env python3
"""
Скрипт для мониторинга процесса обучения в реальном времени
"""
import json
from pathlib import Path
import logging
import time

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def monitor_training():
    """Мониторит процесс обучения в реальном времени"""
    log_dir = Path("../logs")
    if not log_dir.exists():
        logger.error("Директория логов не найдена")
        return
        
    # Ищем последний файл логов
    log_files = list(log_dir.glob("*.json"))
    if not log_files:
        logger.error("Файлы логов не найдены")
        return
        
    latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
    
    logger.info(f"Мониторим файл: {latest_log}")
    
    # Читаем и анализируем логи
    seen_entries = set()
    
    while True:
        try:
            with open(latest_log, 'r') as f:
                lines = f.readlines()
                
            for line in lines:
                if line.strip() and line.strip() not in seen_entries:
                    seen_entries.add(line.strip())
                    log_entry = json.loads(line.strip())
                    
                    if 'loss' in log_entry:
                        logger.info(f"Step {log_entry.get('step', 'N/A')}: "
                                   f"Loss: {log_entry['loss']:.4f}, "
                                   f"Learning Rate: {log_entry.get('learning_rate', 'N/A')}")
                    
            time.sleep(10)  # Проверяем каждые 10 секунд
            
        except KeyboardInterrupt:
            logger.info("Мониторинг прерван пользователем")
            break
        except Exception as e:
            logger.error(f"Ошибка при мониторинге: {str(e)}")
            time.sleep(30)

if __name__ == "__main__":
    monitor_training()