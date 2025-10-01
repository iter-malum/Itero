#!/bin/bash

# Скрипт для запуска всей системы с поддержкой нескольких моделей

echo "=============================================="
echo "Запуск мультиагентной системы Semgrep Rule Engine"
echo "Поддержка нескольких моделей LLM"
echo "=============================================="

# Проверка наличия файла конфигурации
CONFIG_FILE="model_config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Ошибка: Файл конфигурации $CONFIG_FILE не найден!"
    exit 1
fi

# Функция для проверки запуска Ollama
check_ollama_running() {
    if ! curl -s http://localhost:11434/api/tags > /dev/null; then
        echo "Запуск Ollama..."
        ollama serve &
        OLLAMA_PID=$!
        sleep 5
    else
        echo "Ollama уже запущен"
        OLLAMA_PID=""
    fi
}


ensure_ollama_model_loaded() {
    local model_name="$1"
    local purpose="$2"
    
    echo "Проверка модели: $model_name"
    echo "Назначение: $purpose"
    
    if ! ollama list | grep -q "$model_name"; then
        echo "Загрузка модели $model_name..."
        if ollama pull "$model_name"; then
            echo "✅ Модель $model_name успешно загружена"
        else
            echo "❌ Ошибка загрузки модели $model_name"
            return 1
        fi
    else
        echo "✅ Модель $model_name уже загружена"
    fi
    echo "----------------------------------------------"
}

# Функция для создания моделей из локальных Modelfile
ensure_local_model_loaded() {
    local model_name="$1"
    local purpose="$2"
    local modelfile_path="$3"
    
    echo "Проверка локальной модели: $model_name"
    echo "Назначение: $purpose"
    echo "Путь к Modelfile: $modelfile_path"
    
    if ! ollama list | grep -q "$model_name"; then
        if [ -f "$modelfile_path" ]; then
            echo "Создание модели $model_name из $modelfile_path..."
            if ollama create -f "$modelfile_path"; then
                echo "✅ Модель $model_name успешно создана"
            else
                echo "❌ Ошибка создания модели $model_name"
                return 1
            fi
        else
            echo "❌ Modelfile $modelfile_path не найден!"
            return 1
        fi
    else
        echo "✅ Модель $model_name уже загружена"
    fi
    echo "----------------------------------------------"
}

# Основной процесс запуска
main() {
    # Запуск Ollama если не запущен
    check_ollama_running
    
    # Загрузка необходимых моделей из конфигурации
    echo "Загрузка необходимых моделей..."
    
    # Извлекаем модели из конфигурации с помощью jq
    if ! command -v jq &> /dev/null; then
        echo "Установка jq для парсинга JSON..."
        sudo apt-get install -y jq
    fi
    
    # Парсим и загружаем модели
    jq -r '.agents | to_entries[] | "\(.value.model_name)|\(.value.purpose)|\(.value.type)|\(.value.modelfile_path // "")"' "$CONFIG_FILE" | while IFS='|' read model purpose type modelfile_path; do
        if [ -n "$model" ]; then
            if [ "$type" = "local" ]; then
                ensure_local_model_loaded "$model" "$purpose" "$modelfile_path"
            else
                ensure_ollama_model_loaded "$model" "$purpose"
            fi
        fi
    done
    
    # Активация виртуального окружения
    if [ -f "venv_autogen/bin/activate" ]; then
        echo "Активация виртуального окружения..."
        source venv_autogen/bin/activate
    else
        echo "Предупреждение: Виртуальное окружение не найдено"
    fi
    
    # Запуск основной системы
    echo "=============================================="
    echo "Все модели загружены. Запуск основной системы..."
    echo "=============================================="
    python main.py
    
    # Завершение (если мы запускали Ollama, останавливаем его)
    if [ -n "$OLLAMA_PID" ]; then
        echo "Остановка запущенного Ollama..."
        kill $OLLAMA_PID
    fi
}

# Обработка прерываний
trap 'if [ -n "$OLLAMA_PID" ]; then kill $OLLAMA_PID; fi; exit 1' INT TERM

# Запуск основной функции
main