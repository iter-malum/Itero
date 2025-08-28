import autogen
from typing import Dict, Any, Optional
import logging
from utils.prompts import VALIDATION_AGENT_SYSTEM_MESSAGE
from utils.semgrep_runner import SemgrepRunner

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationAgent:
    """
    Агент для валидации правил Semgrep с помощью Semgrep CLI.
    """
    
    def __init__(self, llm_config: Dict[str, Any]):
        """
        Инициализация Validation Agent.
        
        Args:
            llm_config: Конфигурация LLM для AutoGen
        """
        self.llm_config = llm_config
        self.semgrep_runner = SemgrepRunner()
        
        # Создание агента AutoGen
        self.agent = autogen.AssistantAgent(
            name="Validation_Agent",
            system_message=VALIDATION_AGENT_SYSTEM_MESSAGE,
            llm_config=self.llm_config,
        )
        
        # Регистрация функции валидации для использования агентом
        self.register_functions()
        logger.info("Validation Agent инициализирован")

    def register_functions(self):
        """Регистрирует функции, которые может вызывать агент."""
        
        @self.agent.register_for_llm(description="Запуск Semgrep для валидации правила на тестовом коде")
        def validate_rule_with_semgrep(rule_yaml: str, test_code: str, test_type: str = "positive") -> str:
            """
            Выполняет валидацию правила с помощью Semgrep CLI.
            
            Args:
                rule_yaml: YAML-содержимое правила Semgrep
                test_code: Код для тестирования
                test_type: Тип теста ("positive" или "negative")
                
            Returns:
                Строка с результатами выполнения Semgrep
            """
            try:
                result = self.semgrep_runner.run_semgrep(rule_yaml, test_code)
                
                if not result["success"]:
                    return f"Ошибка при выполнении Semgrep ({test_type} тест): {result.get('error', 'Неизвестная ошибка')}"
                
                if test_type == "positive":
                    expected = "обнаружить уязвимость"
                    success = len(result["results"]) > 0
                else:  # negative
                    expected = "НЕ обнаруживать уязвимость"
                    success = len(result["results"]) == 0
                
                status = "УСПЕХ" if success else "НЕУДАЧА"
                
                response = f"""
                ### {test_type.capitalize()} тест:
                - **Результат:** {status} - правило {'' if success else 'НЕ '}{expected}
                - **Количество срабатываний:** {len(result['results'])}
                - **Ошибки:** {len(result.get('errors', []))}
                """
                
                if result["results"]:
                    response += "\n- **Обнаруженные срабатывания:**"
                    for i, match in enumerate(result["results"][:3]):  # Показываем первые 3
                        response += f"\n  {i+1}. {match.get('message', 'Без сообщения')}"
                
                if result.get("errors"):
                    response += "\n- **Ошибки Semgrep:**"
                    for error in result.get("errors", [])[:3]:  # Показываем первые 3 ошибки
                        response += f"\n  - {error.get('message', 'Неизвестная ошибка')}"
                
                return response
                
            except Exception as e:
                error_msg = f"Неожиданная ошибка при валидации правила: {str(e)}"
                logger.error(error_msg)
                return error_msg

    def validate_rule(self, rule_yaml: str, positive_test: str, 
                     negative_test: str, rule_id: str = "unknown") -> Dict[str, Any]:
        """
        Основной метод для валидации правила.
        
        Args:
            rule_yaml: YAML-содержимое правила Semgrep
            positive_test: Код с уязвимостью (должен обнаруживаться)
            negative_test: Код без уязвимости (не должен обнаруживаться)
            rule_id: ID правила для отчетности
            
        Returns:
            Словарь с результатами валидации
        """
        try:
            # Создаем UserProxyAgent для взаимодействия с агентом
            user_proxy = autogen.UserProxyAgent(
                name="User_Proxy",
                human_input_mode="NEVER",
                code_execution_config={"work_dir": "coding", "use_docker": False},
                max_consecutive_auto_reply=2,
            )
            
            # Запускаем валидацию
            user_proxy.initiate_chat(
                self.agent,
                message=f"""
                Протестируй следующее правило Semgrep и предоставь детальный отчет:
                
                ## Правило (ID: {rule_id}):
                ```yaml
                {rule_yaml}
                ```
                
                ## Позитивный тест (код с уязвимостью):
                ```python
                {positive_test}
                ```
                
                ## Негативный тест (код без уязвимости):
                ```python
                {negative_test}
                ```
                
                Протестируй правило на обоих примерах и предоставь вердикт.
                """,
            )
            
            # Получаем ответ агента
            last_message = self.agent.last_message()
            if last_message and "content" in last_message:
                response_content = last_message["content"]
                
                # Также запускаем автоматическую валидацию для объективной оценки
                auto_validation = self.semgrep_runner.validate_rule(
                    rule_yaml, positive_test, negative_test
                )
                
                return {
                    "success": True,
                    "llm_analysis": response_content,
                    "auto_validation": auto_validation,
                    "validation_passed": auto_validation["validation_passed"]
                }
            else:
                return {
                    "success": False,
                    "error": "Агент не вернул ответ",
                    "validation_passed": False
                }
                
        except Exception as e:
            error_msg = f"Ошибка при валидации правила: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "validation_passed": False
            }