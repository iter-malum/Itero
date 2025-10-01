import autogen
import yaml
import re
from typing import Dict, Any, Optional, List
import logging
from utils.prompts import RULE_ENGINEER_AGENT_SYSTEM_MESSAGE
from config.llm_config import RULE_ENGINEER_LLM_CONFIG

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RuleEngineerAgent:
    """
    Агент для создания и модификации правил Semgrep.
    """
    
    def __init__(self, llm_config: Dict[str, Any], model_config: Dict[str, Any] = None):
        self.llm_config = llm_config or RULE_ENGINEER_LLM_CONFIG
        
        # Загрузка дообученной модели если указана в конфиге
        if model_config and model_config.get('type') == 'local_peft':
            from core.model_loader import load_peft_model
            self.model, self.tokenizer = load_peft_model(
                model_config['model_name'],
                model_config['lora_adapters'],
                model_config.get('offload_dir', './offload')
            )
            self.use_fine_tuned_model = True
            logger.info("Rule Engineer Agent с дообученной моделью инициализирован")
        else:
            # Стандартная инициализация с AutoGen
            self.agent = autogen.AssistantAgent(
                name="Rule_Engineer_Agent",
                system_message=RULE_ENGINEER_AGENT_SYSTEM_MESSAGE,
                llm_config=self.llm_config,
            )
            self.use_fine_tuned_model = False
            logger.info("Rule Engineer Agent с AutoGen инициализирован")

        def generate_rule_with_model(self, problem_description: str, code_example: str = None) -> str:
            """Генерирует правило с использованием дообученной модели"""
            if not self.use_fine_tuned_model:
                return self.create_or_update_rule(problem_description, code_example)
            
            # Формируем промпт для модели
            prompt = self._build_rule_generation_prompt(problem_description, code_example)
            
            # Генерируем ответ с помощью модели
            inputs = self.tokenizer(prompt, return_tensors="pt", max_length=2048, truncation=True)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=1024,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Извлекаем YAML из ответа
            yaml_content = self.extract_yaml_from_response(response)
            return yaml_content or response
    
    def _build_rule_generation_prompt(self, problem_description: str, code_example: str = None) -> str:
            """Строит промпт для генерации правил Semgrep"""
            prompt = f"""<s>[INST] Ты - эксперт по безопасности и статическому анализу кода. Создай правило Semgrep для обнаружения следующей уязвимости:

            Описание уязвимости: {problem_description}
            """
                    if code_example:
                        prompt += f"""
            Пример кода с уязвимостью:
            ```python
            {code_example}"""
            prompt += """
                Создай точное и эффективное правило Semgrep в формате YAML. Правило должно:

                Точно обнаруживать указанную уязвимость

                Иметь понятное сообщение (message)

                Указать правильную степень серьезности (severity)

                Использовать соответствующие языки (languages)

                Верни только YAML-правило без дополнительных комментариев. [/INST]
                """
            return prompt
    def extract_yaml_from_response(self, response: str) -> Optional[str]:
        """
        Извлекает YAML-блок из ответа агента.
        
        Args:
            response: Ответ агента, который может содержать YAML-блок
            
        Returns:
            Извлеченный YAML или None, если не найден
        """
        # Ищем YAML-блок между ```yaml и ```
        yaml_pattern = r"```yaml\s*(.*?)\s*```"
        match = re.search(yaml_pattern, response, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # Если не нашли с пометкой yaml, попробуем найти любой код-блок
        code_pattern = r"```\s*(.*?)\s*```"
        match = re.search(code_pattern, response, re.DOTALL)
        
        if match:
            # Проверим, выглядит ли содержимое как YAML
            content = match.group(1).strip()
            if content.startswith("rules:") or "id:" in content and "message:" in content:
                return content
        
        logger.warning("Не удалось извлечь YAML из ответа агента")
        return None

    def validate_yaml(self, yaml_content: str) -> bool:
        """
        Проверяет валидность YAML-содержимого.
        
        Args:
            yaml_content: YAML-строка для проверки
            
        Returns:
            True если YAML валиден, иначе False
        """
        try:
            yaml.safe_load(yaml_content)
            return True
        except yaml.YAMLError as e:
            logger.error(f"Невалидный YAML: {str(e)}")
            return False

    def refine_existing_rule(self, base_rule_yaml: str, problem_description: str, 
                        code_example: str = None, original_rule_id: str = None) -> Dict[str, Any]:
        """
        Дорабатывает существующее правило на основе нового описания проблемы.
        
        Args:
            base_rule_yaml: YAML существующего правила
            problem_description: Описание новой уязвимости
            code_example: Пример кода с уязвимостью (опционально)
            original_rule_id: ID оригинального правила (для отслеживания)
            
        Returns:
            Словарь с результатом доработки
        """
        try:
            # Создаем UserProxyAgent для взаимодействия
            user_proxy = autogen.UserProxyAgent(
                name="User_Proxy",
                human_input_mode="NEVER",
                code_execution_config={"work_dir": "coding", "use_docker": False},
                max_consecutive_auto_reply=2,
            )
            
            # Формируем специализированное сообщение для доработки
            message = f"""
            НЕОБХОДИМО ДОРАБОТАТЬ СУЩЕСТВУЮЩЕЕ ПРАВИЛО SEMGREP:

            ОРИГИНАЛЬНОЕ ПРАВИЛО (ID: {original_rule_id or 'unknown'}):
            ```yaml
            {base_rule_yaml}
            ```

            НОВАЯ УЯЗВИМОСТЬ ДЛЯ ОБНАРУЖЕНИЯ:
            {problem_description}
            """
            
            if code_example:
                message += f"""

            ПРИМЕР КОДА С НОВОЙ УЯЗВИМОСТЬЮ:
            ```python
            {code_example}
            ```
            """
            
            message += """

            ЗАДАЧА:
            - Сохраните структуру и формат оригинального правила
            - Добавьте необходимые паттерны для обнаружения новой уязвимости
            - Не удаляйте существующую функциональность правила
            - Обновите ID правила, добавив суффикс (например, "_enhanced")
            - При необходимости обновите поле message, чтобы отразить расширенную функциональность

            Верните только доработанное YAML-правило без дополнительных комментариев.
            """
            
            # Запускаем диалог
            user_proxy.initiate_chat(
                self.agent,
                message=message,
            )
            
            # Получаем и обрабатываем ответ агента
            last_message = self.agent.last_message()
            if last_message and "content" in last_message:
                response_content = last_message["content"]
                
                # Извлекаем YAML из ответа
                yaml_content = self.extract_yaml_from_response(response_content)
                
                if yaml_content and self.validate_yaml(yaml_content):
                    return {
                        'success': True,
                        'rule_yaml': yaml_content,
                        'message': "Правило успешно доработано",
                        'is_new': False,  # Это доработанное правило
                        'original_rule_id': original_rule_id
                    }
                else:
                    return {
                        'success': False,
                        'rule_yaml': None,
                        'message': "Не удалось извлечь валидный YAML из ответа агента при доработке",
                        'is_new': False
                    }
            else:
                return {
                    'success': False,
                    'rule_yaml': None,
                    'message': "Агент не вернул ответ при доработке правила",
                    'is_new': False
                }
                
        except Exception as e:
            error_msg = f"Ошибка при доработке правила: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'rule_yaml': None,
                'message': error_msg,
                'is_new': False
            }

    def create_or_update_rule(self, problem_description: str, code_example: str = None, 
                             similar_rules: List[Dict] = None) -> Dict[str, Any]:
        """
        Создает новое правило или обновляет существующее на основе описания проблемы.
        
        Args:
            problem_description: Описание уязвимости
            code_example: Пример кода с уязвимостью (опционально)
            similar_rules: Список похожих правил (опционально)
            
        Returns:
            Словарь с результатом: {
                'success': bool,
                'rule_yaml': str,  # YAML-содержимое правила
                'message': str,    # Сообщение об ошибке или успехе
                'is_new': bool     # True если правило новое, False если обновление
            }
        """
        try:
            # Создаем UserProxyAgent для взаимодействия с агентом
            user_proxy = autogen.UserProxyAgent(
                name="User_Proxy",
                human_input_mode="NEVER",
                code_execution_config={"work_dir": "coding", "use_docker": False},
                max_consecutive_auto_reply=2,
            )
            
            # Формируем сообщение для агента
            message = f"""
            Необходимо создать или обновить правило Semgrep для обнаружения следующей уязвимости:
            
            Описание: {problem_description}
            """
            
            if code_example:
                message += f"""
                
            Пример кода с уязвимостью:
            ```python
            {code_example}
            ```
            """
            
            if similar_rules:
                message += "\n\nПохожие правила из базы данных:\n"
                for i, rule in enumerate(similar_rules):
                    message += f"\n{i+1}. ID: {rule.get('id', 'N/A')}\n"
                    message += f"   Message: {rule.get('message', 'N/A')}\n"
                    message += f"   Source: {rule.get('source_file', 'N/A')}\n"
            
            message += "\nПожалуйста, создай новое правило или модифицируй самое подходящее из похожих правил."
            
            # Запускаем диалог
            user_proxy.initiate_chat(
                self.agent,
                message=message,
            )
            
            # Получаем ответ агента
            last_message = self.agent.last_message()
            if last_message and "content" in last_message:
                response_content = last_message["content"]
                
                # Извлекаем YAML из ответа
                yaml_content = self.extract_yaml_from_response(response_content)
                
                if yaml_content and self.validate_yaml(yaml_content):
                    # Определяем, новое это правило или обновление
                    is_new = similar_rules is None or len(similar_rules) == 0
                    
                    return {
                        'success': True,
                        'rule_yaml': yaml_content,
                        'message': "Правило успешно создано/обновлено",
                        'is_new': is_new
                    }
                else:
                    return {
                        'success': False,
                        'rule_yaml': None,
                        'message': "Не удалось извлечь валидный YAML из ответа агента",
                        'is_new': False
                    }
            else:
                return {
                    'success': False,
                    'rule_yaml': None,
                    'message': "Агент не вернул ответ",
                    'is_new': False
                }
                
        except Exception as e:
            error_msg = f"Ошибка при создании/обновлении правила: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'rule_yaml': None,
                'message': error_msg,
                'is_new': False
            }

    def save_rule_to_file(self, yaml_content: str, filename: str = None) -> str:
        """
        Сохраняет правило в YAML-файл.
        
        Args:
            yaml_content: YAML-содержимое правила
            filename: Имя файла (опционально)
            
        Returns:
            Путь к сохраненному файлу
        """
        import os
        from datetime import datetime
        
        # Создаем директорию для правил, если ее нет
        rules_dir = "./data/generated_rules"
        os.makedirs(rules_dir, exist_ok=True)
        
        # Генерируем имя файла, если не предоставлено
        if filename is None:
            # Пытаемся извлечь ID правила из YAML
            rule_data = yaml.safe_load(yaml_content)
            if rule_data and 'rules' in rule_data and len(rule_data['rules']) > 0:
                rule_id = rule_data['rules'][0].get('id', 'unknown')
                filename = f"{rule_id}.yaml"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"new_rule_{timestamp}.yaml"
        
        filepath = os.path.join(rules_dir, filename)
        
        # Сохраняем правило в файл
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(yaml_content)
        
        logger.info(f"Правило сохранено в файл: {filepath}")
        return filepath