#!/bin/bash

# Скрипт для запуска всей системы

echo "=============================================="
echo "Запуск мультиагентной системы Semgrep Rule Engine"
echo "=============================================="

# Проверка, запущен ли Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "Запуск Ollama..."
    ollama serve &
    OLLAMA_PID=$!
    sleep 5  # Даем время на запуск
fi

# Проверка, загружена ли модель
if ! ollama list | grep -q "deepseek-coder:6.7b"; then
    echo "Загрузка модели deepseek-coder:6.7b..."
    ollama pull deepseek-coder:6.7b
fi

# Активация виртуального окружения
source venv_autogen/bin/activate

# Запуск основной системы
echo "Запуск основной системы..."
python main.py

# Если мы запускали Ollama, останавливаем его
if [ ! -z "$OLLAMA_PID" ]; then
    echo "Остановка Ollama..."
    kill $OLLAMA_PID
fi