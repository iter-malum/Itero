"""
Конфигурация LLM для AutoGen с использованием дообученной модели.
"""

# Базовая конфигурация
LLM_CONFIG = {
    "config_list": [
        {
            "model": "codellama/CodeLlama-7b-hf",  # Ваша дообученная модель
            "base_url": "http://localhost:11434/v1",  # Или ваш endpoint
            "api_key": "ollama",
        }
    ],
    "temperature": 0.1,
    "timeout": 120,
    "cache_seed": 42
}

# Специализированная конфигурация для RuleEngineerAgent
RULE_ENGINEER_LLM_CONFIG = {
    "config_list": [
        {
            "model": "codeLlama-7b-semgrep-lora",  # Приоритет для дообученной модели
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama",
        }
    ],
    "temperature": 0.3,  # Более высокая температура для креативности
    "timeout": 180,  # Больше времени для сложных правил
    "cache_seed": 42,
    "max_tokens": 4000  # Увеличить лимит для сложных правил
}

def create_agent_configs():
    """Создает конфигурации для каждого агента с их специфичными моделями"""
    
    with open('model_config.json', 'r') as f:
        model_config = json.load(f)
    
    agent_configs = {}
    for agent_name, config in model_config['agents'].items():
        agent_configs[agent_name] = {
            "config_list": [
                {
                    "model": config['model_name'],
                    "base_url": "http://localhost:11434/v1",
                    "api_key": "ollama",
                }
            ],
            "temperature": 0.1 if "search" in agent_name.lower() else 0.3,
            "timeout": 120
        }
    
    return agent_configs