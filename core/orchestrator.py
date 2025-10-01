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
        self.llm_config = LLM_CONFIG
        
        # Загружаем конфигурацию моделей
        with open('model_config.json', 'r') as f:
            self.model_config = json.load(f)
        
        # Инициализация менеджера векторной БД
        self.vector_db_manager = VectorDBManager()
        
        # Инициализация агентов с конфигурацией моделей
        self.search_agent = SearchAgent(self.llm_config, self.vector_db_manager)
        self.rule_engineer_agent = RuleEngineerAgent(
            self.llm_config, 
            self.model_config['agents']['Rule_Engineer_Agent']
        )
        self.validation_agent = ValidationAgent(self.llm_config)
        
        logger.info("Orchestrator инициализирован с дообученной моделью")

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

    def run_interactive_creation_flow(self, code_snippet: str, vulnerability_description: str) -> Dict[str, Any]:
        """
        Новый workflow с выбором пользователя: доработать правило или создать новое.
        
        Args:
            code_snippet: Код с уязвимостью
            vulnerability_description: Описание уязвимости
            
        Returns:
            Словарь с результатами workflow
        """
        logger.info(f"Запуск интерактивного workflow для: {vulnerability_description}")
        
        # Шаг 1: Поиск существующих правил
        logger.info("Шаг 1: Поиск существующих правил...")
        search_result_str = self.search_agent.find_relevant_rules(vulnerability_description, n_results=5)
        
        # Шаг 2: Парсинг результатов поиска для показа пользователю
        similar_rules_parsed = self._parse_search_results(search_result_str)
        
        # Шаг 3: Диалог с пользователем
        print("\n" + "=" * 50)
        print("НАЙДЕНЫ СЛЕДУЮЩИЕ ПОХОЖИЕ ПРАВИЛА:")
        for i, rule in enumerate(similar_rules_parsed):
            print(f"{i+1}. ID: {rule['id']}")
            print(f"   Сообщение: {rule['message']}")
            print(f"   Степень соответствия: {rule.get('similarity', 'N/A')}")
            print()
        
        print(f"{len(similar_rules_parsed)+1}. 📝 СОЗДАТЬ НОВОЕ ПРАВИЛО С НУЛЯ")
        print("=" * 50)
        
        try:
            choice = int(input("\nВыберите опцию (введите номер): "))
        except ValueError:
            print("❌ Некорректный ввод. Создается новое правило.")
            choice = len(similar_rules_parsed) + 1
        
        # Шаг 4: Обработка выбора пользователя
        if 1 <= choice <= len(similar_rules_parsed):
            # Пользователь выбрал доработку правила
            selected_rule = similar_rules_parsed[choice-1]
            logger.info(f"Пользователь выбрал доработать правило: {selected_rule['id']}")
            
            # Загружаем полное YAML-содержимое выбранного правила
            full_rule_yaml = self.vector_db_manager.get_rule_yaml_by_id(selected_rule['id'])
            
            if not full_rule_yaml:
                return {
                    "success": False,
                    "error": f"Не удалось загрузить правило с ID: {selected_rule['id']}",
                    "step": "rule_loading"
                }
            
            # Передаем агенту на доработку
            rule_result = self.rule_engineer_agent.refine_existing_rule(
                base_rule_yaml=full_rule_yaml,
                problem_description=vulnerability_description,
                code_example=code_snippet,
                original_rule_id=selected_rule['id']
            )
        else:
            # Пользователь выбрал создание нового правила
            logger.info("Пользователь выбрал создание нового правила с нуля")
            rule_result = self.rule_engineer_agent.create_or_update_rule(
                problem_description=vulnerability_description,
                code_example=code_snippet,
                similar_rules=None  # Создаем с нуля
            )
        
        # Проверяем успешность создания/доработки правила
        if not rule_result["success"]:
            return {
                "success": False,
                "error": rule_result["message"],
                "step": "rule_creation"
            }
        
        # Шаг 5: Подготовка тестовых примеров и валидация
        logger.info("Шаг 5: Подготовка тестовых примеров...")
        positive_test = self.create_positive_test_case(code_snippet, vulnerability_description)
        negative_test = self.create_negative_test_case(code_snippet, vulnerability_description)
        
        logger.info("Шаг 6: Валидация правила...")
        validation_result = self.validation_agent.validate_rule(
            rule_yaml=rule_result["rule_yaml"],
            positive_test=positive_test,
            negative_test=negative_test,
            rule_id=rule_result.get("rule_id", "new_rule")
        )
        
        # Шаг 7: Сохранение правила
        logger.info("Шаг 7: Сохранение правила...")
        if validation_result.get("validation_passed", False):
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
            logger.warning("Правило не прошло валидацию, но будет сохранено для анализа")
        
        # Формируем финальный результат
        result = {
            "success": True,
            "user_choice": "refine" if 1 <= choice <= len(similar_rules_parsed) else "create_new",
            "selected_rule_id": similar_rules_parsed[choice-1]["id"] if 1 <= choice <= len(similar_rules_parsed) else None,
            "search_result": search_result_str,
            "rule_creation_success": rule_result["success"],
            "validation_passed": validation_result.get("validation_passed", False),
            "rule_yaml": rule_result["rule_yaml"],
            "validation_report": validation_result.get("llm_analysis", ""),
            "saved_path": saved_path,
            "is_new_rule": rule_result.get("is_new", True)
        }
        
        logger.info("Интерактивный workflow завершен!")
        return result
    def _parse_search_results(self, search_result_str: str) -> List[Dict]:
        """
        Парсит строку с результатами поиска в структурированный список правил.
        
        Args:
            search_result_str: Строка с результатами поиска от SearchAgent
            
        Returns:
            Список словарей с информацией о правилах
        """
        similar_rules = []
        
        try:
            # Разбиваем результат на строки и парсим
            lines = search_result_str.split('\n')
            current_rule = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith('ID:'):
                    if current_rule and 'id' in current_rule:
                        similar_rules.append(current_rule)
                    current_rule = {'id': line.replace('ID:', '').strip()}
                elif line.startswith('Message:'):
                    current_rule['message'] = line.replace('Message:', '').strip()
                elif line.startswith('Similarity:'):
                    similarity_str = line.replace('Similarity:', '').strip()
                    try:
                        current_rule['similarity'] = float(similarity_str)
                    except ValueError:
                        current_rule['similarity'] = similarity_str
                elif line.startswith('Source:'):
                    current_rule['source'] = line.replace('Source:', '').strip()
            
            # Добавляем последнее правило
            if current_rule and 'id' in current_rule:
                similar_rules.append(current_rule)
                
        except Exception as e:
            logger.error(f"Ошибка при парсинге результатов поиска: {str(e)}")
        
        return similar_rules

def main():
    """Основная функция для запуска оркестратора."""
    orchestrator = Orchestrator()
    orchestrator.run_interactive_workflow()

if __name__ == "__main__":
    main()