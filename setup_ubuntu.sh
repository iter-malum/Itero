#!/bin/bash

# Скрипт установки и настройки для мультиагентной системы Semgrep Rule Engine
# Для Ubuntu 22.04 LTS

set -e  # Прерывать выполнение при ошибке

echo "=============================================="
echo "Установка мультиагентной системы Semgrep Rule Engine"
echo "=============================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для проверки успешности выполнения команды
check_success() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Успешно!${NC}"
    else
        echo -e "${RED}Ошибка!${NC}"
        exit 1
    fi
}

# Функция для установки пакетов с проверкой
install_package() {
    echo -n "Установка $1... "
    sudo apt-get install -y $1 > /dev/null 2>&1
    check_success
}

# Обновление системы
echo -n "Обновление списка пакетов... "
sudo apt-get update > /dev/null 2>&1
check_success

# Установка необходимых системных пакетов
echo "Установка системных зависимостей..."
install_package python3.11
install_package python3.11-venv
install_package python3-pip
install_package curl
install_package wget
install_package git

# Установка Ollama
echo -n "Установка Ollama... "
curl -fsSL https://ollama.ai/install.sh | sh > /dev/null 2>&1
check_success

# Запуск Ollama как сервиса
echo -n "Запуск Ollama сервиса... "
sudo systemctl start ollama > /dev/null 2>&1
sudo systemctl enable ollama > /dev/null 2>&1
check_success

# Загрузка модели deepseek-coder
echo -n "Загрузка модели deepseek-coder:6.7b... "
ollama pull deepseek-coder:6.7b > /dev/null 2>&1 &
OLAMA_PID=$!
# Ждем завершения загрузки с таймаутом
sleep 30
if ps -p $OLAMA_PID > /dev/null; then
    echo -e "${YELLOW}Загрузка модели все еще выполняется в фоне...${NC}"
else
    check_success
fi

# Создание виртуального окружения Python
echo -n "Создание виртуального окружения... "
python3.11 -m venv venv_autogen > /dev/null 2>&1
check_success

# Активация виртуального окружения
echo -n "Активация виртуального окружения... "
source venv_autogen/bin/activate
check_success

# Установка Python зависимостей
echo -n "Установка Python зависимостей... "
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
check_success

# Создание структуры папок
echo -n "Создание структуры папок... "
mkdir -p data/raw_rules data/generated_rules logs tests scripts agents core utils config > /dev/null 2>&1
check_success

# Клонирование официального репозитория правил Semgrep
echo -n "Клонирование официального репозитория semgrep-rules... "
git clone https://github.com/semgrep/semgrep-rules.git data/official_rules > /dev/null 2>&1
check_success

# Копирование правил в raw_rules
echo -n "Копирование официальных правил в рабочую директорию... "
cp -r data/official_rules/* data/raw_rules/ > /dev/null 2>&1
check_success

# Удаление временных файлов (опционально)
echo -n "Очистка временных файлов... "
rm -rf data/official_rules/.git data/official_rules/README.md > /dev/null 2>&1
check_success

# Построение векторной базы данных
echo -n "Построение векторной базы данных... "
python scripts/build_vector_db.py > /dev/null 2>&1
check_success

# Запуск тестов
echo "Запуск тестов..."
echo "1. Тестирование Search Agent..."
python tests/test_search_agent.py

echo "2. Тестирование Rule Engineer Agent..."
python tests/test_rule_engineer_agent.py

echo "3. Тестирование Validation Agent..."
python tests/test_validation_agent.py

echo "4. Тестирование полного workflow..."
python tests/test_full_workflow.py

echo "=============================================="
echo -e "${GREEN}Установка и настройка завершены!${NC}"
echo "=============================================="
echo ""
echo "Для запуска системы выполните:"
echo "  source venv_autogen/bin/activate"
echo "  python main.py"
echo ""
echo "Для запуска Ollama (если не запущен):"
echo "  ollama serve"
echo "  ollama run deepseek-coder:6.7b"
echo ""
echo "Для остановки Ollama:"
echo "  sudo systemctl stop ollama"
echo "=============================================="