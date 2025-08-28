import autogen
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import os

from agents.search_agent import SearchAgent
from agents.rule_engineer_agent import RuleEngineerAgent
from agents.validation_agent import ValidationAgent
from utils.vector_db_manager import VectorDBManager
from config.llm_config import LLM_CONFIG

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Orchestrator:
    """
    Главный оркестратор, который управляет всеми агентами и workflow.
    """
    
    def __init__(self):
        """Инициализация всех компонентов системы."""
        self.llm_config = LLM_CONFIG
        
        # Инициализация менеджера векторной БД
        self.vector_db_manager = VectorDBManager()
        
        # Инициализация агентов
        self.search_agent = SearchAgent(self.llm_config, self.vector_db_manager)
        self.rule_engineer_agent = RuleEngineerAgent(self.llm_config)
        self.validation_agent = ValidationAgent(self.llm_config)
        
        # Создание UserProxyAgent для управления диалогом
        self.user_proxy = autogen.UserProxyAgent(
            name="User_Proxy",
            human_input_mode="NEVER",
            code_execution_config={"work_dir": "coding", "use_docker": False},
            max_consecutive_auto_reply=10,
            human_input_mode="NEVER",
        )
        
        logger.info("Orchestrator инициализирован со всеми агентами")

    def create_positive_test_case(self, code_snippet: str, vulnerability_description: str) -> str:
        """
        Создает позитивный тестовый пример на основе кода и описания уязвимости.
        
        Args:
            code_snippet: Исходный код с уязвимостью
            vulnerability_description: Описание уязвимости
            
        Returns:
            Готовый тестовый пример
        """
        # В реальной системе здесь может быть более сложная логика
        # Для простоты возвращаем исходный код как есть
        return code_snippet

    def create_negative_test_case(self, code_snippet: str, vulnerability_description: str) -> str:
        """
        Создает негативный тестовый пример (код без уязвимости).
        
        Args:
            code_snippet: Исходный код с уязвимостью
            vulnerability_description: Описание уязвимости
            
        Returns:
            Готовый тестовый пример без уязвимости
        """
        # В реальной системе здесь может быть генерация "чистого" кода
        # или использование шаблонов. Для простоты возвращаем упрощенную версию
        if "sql" in vulnerability_description.lower():
            return "query = \"SELECT * FROM users WHERE status = 'active'\""
        elif "xss" in vulnerability_description.lower():
            return "element.textContent = userInput"
        else:
            return "# Чистый код без уязвимостей\nresult = safe_function()"

    def run_full_workflow(self, code_snippet: str, vulnerability_description: str) -> Dict[str, Any]:
        """
        Запускает полный workflow обработки запроса.
        
        Args:
            code_snippet: Код с уязвимостью
            vulnerability_description: Описание уязвимости
            
        Returns:
            Словарь с результатами workflow
        """
        logger.info(f"Запуск полного workflow для: {vulnerability_description}")
        
        # Шаг 1: Поиск существующих правил
        logger.info("Шаг 1: Поиск существующих правил...")
        search_result = self.search_agent.find_relevant_rules(vulnerability_description)
        
        # Извлекаем информацию о найденных правилах
        similar_rules = []
        if "Найдены следующие релевантные правила" in search_result:
            # Парсим результаты поиска для передачи агенту-инженеру
            lines = search_result.split("\n")
            for line in lines:
                if line.strip().startswith("ID:"):
                    rule_id = line.split("ID:")[1].split("\n")[0].strip()
                    similar_rules.append({"id": rule_id})
        
        # Шаг 2: Создание или обновление правила
        logger.info("Шаг 2: Создание/обновление правила...")
        rule_result = self.rule_engineer_agent.create_or_update_rule(
            problem_description=vulnerability_description,
            code_example=code_snippet,
            similar_rules=similar_rules if similar_rules else None
        )
        
        if not rule_result["success"]:
            return {
                "success": False,
                "error": rule_result["message"],
                "step": "rule_creation"
            }
        
        # Шаг 3: Подготовка тестовых примеров
        logger.info("Шаг 3: Подготовка тестовых примеров...")
        positive_test = self.create_positive_test_case(code_snippet, vulnerability_description)
        negative_test = self.create_negative_test_case(code_snippet, vulnerability_description)
        
        # Шаг 4: Валидация правила
        logger.info("Шаг 4: Валидация правила...")
        validation_result = self.validation_agent.validate_rule(
            rule_yaml=rule_result["rule_yaml"],
            positive_test=positive_test,
            negative_test=negative_test,
            rule_id=rule_result.get("rule_id", "new_rule")
        )
        
        if not validation_result["success"]:
            return {
                "success": False,
                "error": validation_result.get("error", "Ошибка валидации"),
                "step": "validation",
                "rule_yaml": rule_result["rule_yaml"]  # Все равно возвращаем правило
            }
        
        # Шаг 5: Сохранение успешного правила
        logger.info("Шаг 5: Сохранение правила...")
        if validation_result.get("validation_passed", False):
            # Извлекаем ID правила из YAML для имени файла
            try:
                import yaml
                rule_data = yaml.safe_load(rule_result["rule_yaml"])
                rule_id = rule_data["rules"][0]["id"] if rule_data and "rules" in rule_data else "new_rule"
                filename = f"{rule_id}.yaml"
            except:
                filename = None
                
            saved_path = self.rule_engineer_agent.save_rule_to_file(
                rule_result["rule_yaml"], filename
            )
        else:
            saved_path = None
        
        # Формируем финальный результат
        result = {
            "success": True,
            "search_result": search_result,
            "rule_creation_success": rule_result["success"],
            "validation_passed": validation_result.get("validation_passed", False),
            "rule_yaml": rule_result["rule_yaml"],
            "validation_report": validation_result.get("llm_analysis", ""),
            "saved_path": saved_path,
            "is_new_rule": rule_result.get("is_new", True)
        }
        
        logger.info("Workflow завершен успешно!")
        return result

    def run_interactive_workflow(self):
        """
        Запускает интерактивный режим работы с пользователем.
        """
        print("=" * 60)
        print("МУЛЬТИАГЕНТНАЯ СИСТЕМА ДЛЯ СОЗДАНИЯ ПРАВИЛ SEMGREP")
        print("=" * 60)
        
        while True:
            print("\nВведите описание уязвимости (или 'quit' для выхода):")
            description = input().strip()
            
            if description.lower() == 'quit':
                break
                
            print("\nВведите код с уязвимостью (завершите пустой строкой):")
            code_lines = []
            while True:
                line = input()
                if line.strip() == "":
                    break
                code_lines.append(line)
            
            code_snippet = "\n".join(code_lines)
            
            if not code_snippet:
                print("Код не может быть пустым!")
                continue
                
            print("\nОбработка запроса...")
            result = self.run_full_workflow(code_snippet, description)
            
            print("\n" + "=" * 40)
            print("РЕЗУЛЬТАТЫ ОБРАБОТКИ")
            print("=" * 40)
            
            if result["success"]:
                print("✓ Workflow завершен успешно!")
                print(f"\nПоиск: Найдено {result['search_result'].count('ID:')} релевантных правил")
                print(f"Создание правила: {'Успех' if result['rule_creation_success'] else 'Неудача'}")
                print(f"Валидация: {'Пройдена' if result['validation_passed'] else 'Не пройдена'}")
                print(f"Тип: {'Новое правило' if result['is_new_rule'] else 'Обновление правила'}")
                
                if result["saved_path"]:
                    print(f"Сохранено в: {result['saved_path']}")
                    
                print("\nОтчет о валидации:")
                print(result["validation_report"])
                
                print("\nСодержимое правила:")
                print(result["rule_yaml"])
            else:
                print("✗ Workflow завершен с ошибкой:")
                print(f"Этап: {result.get('step', 'unknown')}")
                print(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")
                
                if "rule_yaml" in result:
                    print("\nЧастично созданное правило:")
                    print(result["rule_yaml"])
            
            print("\n" + "=" * 40)

def main():
    """Основная функция для запуска оркестратора."""
    orchestrator = Orchestrator()
    orchestrator.run_interactive_workflow()

if __name__ == "__main__":
    main()