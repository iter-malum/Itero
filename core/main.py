#!/usr/bin/env python3
"""
Главная точка входа в приложение.
Запуск: python main.py
"""

import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.orchestrator import main

if __name__ == "__main__":
    main()