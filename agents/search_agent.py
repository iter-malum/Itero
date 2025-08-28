import autogen
from typing import Optional, Dict, Any
import logging
from utils.prompts import SEARCH_AGENT_SYSTEM_MESSAGE

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SearchAgent:
    """
    Агент для поиска релевантных правил в векторной БД на основе описания уязвимости.
    """
    
    def __init__(self, llm_config: Dict[str, Any], vector_db_manager):
        """
        Инициализация Search Agent.
        
        Args:
            llm_config: Конфигурация LLM для AutoGen
            vector_db_manager: Экземпляр VectorDBManager для доступа к векторной БД
        """
        self.llm_config = llm_config
        self.vector_db_manager = vector_db_manager
        
        # Создание агента AutoGen
        self.agent = autogen.AssistantAgent(
            name="Search_Agent",
            system_message=SEARCH_AGENT_SYSTEM_MESSAGE,
            llm_config=self.llm_config,
        )
        
        # Регистрация функции поиска для использования агентом
        self.register_functions()
        logger.info("Search Agent инициализирован")

    def register_functions(self):
        """Регистрирует функции, которые может вызывать агент."""
        
        @self.agent.register_for_llm(description="Поиск релевантных правил в базе данных по текстовому запросу")
        def query_rules(query_text: str, n_results: int = 5) -> str:
            """
            Выполняет поиск правил по текстовому запросу.
            
            Args:
                query_text: Текст запроса для поиска
                n_results: Количество возвращаемых результатов
                
            Returns:
                Строка с результатами поиска
            """
            try:
                results = self.vector_db_manager.query_rules(query_text, n_results)
                
                if not results:
                    return "По вашему запросу не найдено ни одного правила."
                
                # Форматируем результаты в читаемый вид
                formatted_results = []
                for i, result in enumerate(results):
                    formatted_results.append(
                        f"{i+1}. ID: {result['id']}\n"
                        f"   Message: {result['metadata']['message']}\n"
                        f"   Severity: {result['metadata']['severity']}\n"
                        f"   Source: {result['metadata']['source_file']}\n"
                        f"   Similarity: {result['distance']:.4f}\n"
                    )
                
                return "Найдены следующие релевантные правила:\n\n" + "\n".join(formatted_results)
                
            except Exception as e:
                error_msg = f"Ошибка при выполнении поиска: {str(e)}"
                logger.error(error_msg)
                return error_msg

    def formulate_search_query(self, problem_description: str) -> str:
        """
        Формулирует поисковый запрос на основе описания проблемы.
        
        Args:
            problem_description: Описание уязвимости или проблемы
            
        Returns:
            Сформулированный поисковый запрос
        """
        try:
            # Создаем UserProxyAgent для взаимодействия с Search Agent
            user_proxy = autogen.UserProxyAgent(
                name="User_Proxy",
                human_input_mode="NEVER",
                code_execution_config={"work_dir": "coding", "use_docker": False},
                max_consecutive_auto_reply=1,
            )
            
            # Запускаем диалог для формулирования поискового запроса
            user_proxy.initiate_chat(
                self.agent,
                message=f"""
                Проанализируй следующее описание уязвимости и сформулируй точный поисковый запрос для базы правил:
                
                {problem_description}
                
                Верни только поисковый запрос без дополнительных комментариев.
                """,
            )
            
            # Получаем последний ответ агента
            last_message = self.agent.last_message()
            if last_message and "content" in last_message:
                return last_message["content"].strip()
            else:
                logger.warning("Агент не вернул поисковый запрос")
                return problem_description  # Fallback - используем исходное описание
                
        except Exception as e:
            logger.error(f"Ошибка при формулировании поискового запроса: {str(e)}")
            return problem_description  # Fallback - используем исходное описание

    def find_relevant_rules(self, problem_description: str, n_results: int = 5) -> str:
        """
        Основной метод для поиска релевантных правил.
        
        Args:
            problem_description: Описание уязвимости или проблемы
            n_results: Количество возвращаемых результатов
            
        Returns:
            Строка с результатами поиска
        """
        # Сначала формулируем оптимальный поисковый запрос
        search_query = self.formulate_search_query(problem_description)
        logger.info(f"Сформулирован поисковый запрос: '{search_query}'")
        
        # Затем выполняем поиск по векторной БД
        try:
            results = self.vector_db_manager.query_rules(search_query, n_results)
            
            if not results:
                return "По вашему запросу не найдено ни одного правила."
            
            # Форматируем результаты в читаемый вид
            formatted_results = []
            for i, result in enumerate(results):
                formatted_results.append(
                    f"{i+1}. ID: {result['id']}\n"
                    f"   Message: {result['metadata']['message']}\n"
                    f"   Severity: {result['metadata']['severity']}\n"
                    f"   Source: {result['metadata']['source_file']}\n"
                    f"   Similarity: {result['distance']:.4f}\n"
                )
            
            return "Найдены следующие релевантные правила:\n\n" + "\n".join(formatted_results)
            
        except Exception as e:
            error_msg = f"Ошибка при выполнении поиска: {str(e)}"
            logger.error(error_msg)
            return error_msg