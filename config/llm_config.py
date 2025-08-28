"""
Конфигурация LLM для AutoGen.
"""

LLM_CONFIG = {
    "config_list": [
        {
            "model": "deepseek-coder:6.7b",
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama",
        }
    ],
    "temperature": 0.1,
    "timeout": 120,
    "cache_seed": 42  # Для воспроизводимости результатов
}

# Конфигурация для агента-инженера (более высокая температура для креативности)
RULE_ENGINEER_LLM_CONFIG = {
    "config_list": LLM_CONFIG["config_list"],
    "temperature": 0.3,  # Более высокая температура для креативности
    "timeout": 180,  # Больше времени для генерации сложных правил
    "cache_seed": 42
}