#!/bin/bash

# Скрипт для запуска всех тестов

set -e  # Прерывать выполнение при ошибке

echo "=============================================="
echo "Запуск тестов мультиагентной системы"
echo "=============================================="

# Активация виртуального окружения
source venv_autogen/bin/activate

# Запуск тестов
echo "1. Запуск тестов Search Agent..."
python tests/test_search_agent.py

echo ""
echo "2. Запуск тестов Rule Engineer Agent..."
python tests/test_rule_engineer_agent.py

echo ""
echo "3. Запуск тестов Validation Agent..."
python tests/test_validation_agent.py

echo ""
echo "4. Запуск тестов полного workflow..."
python tests/test_full_workflow.py

echo ""
echo "=============================================="
echo "Все тесты завершены!"
echo "=============================================="