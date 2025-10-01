import os
import yaml
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorDBManager:
    """
    Класс для управления векторной базой данных правил Semgrep.
    Отвечает за создание, наполнение и запросы к векторной БД.
    """
    def get_rule_yaml_by_id(self, rule_id: str) -> str:
        """
        Ищет и возвращает полное YAML-содержимое исходного файла правила по его ID.
        Это критически важно для функции доработки существующих правил.
        
        Args:
            rule_id (str): ID правила, которое нужно найти.
            
        Returns:
            str: YAML-содержимое правила в виде строки.
        """
        # Вам нужно реализовать логику поиска файла по rule_id и чтения его содержимого.
        # Это может потребовать предварительного индексирования путей к файлам.
        # Примерный алгоритм:
        # 1. Найдите файл, содержащий правило с данным ID (возможно, потребуется 
        #    сохранить эту информацию в метаданных векторной БД или вести отдельный индекс)
        # 2. Прочитайте содержимое найденного YAML-файла
        # 3. Верните его как строку
        #
        # ЗАМЕНИТЕ ЭТУ ЗАГЛУШКУ НА РЕАЛЬНУЮ ЛОГИКУ ПОИСКА В ВАШЕЙ ФАЙЛОВОЙ СИСТЕМЕ
        try:
            # Пример: если у вас есть словарь, отображающий rule_id в путь к файлу
            # file_path = self.rule_id_to_path_mapping.get(rule_id)
            # if file_path and os.path.exists(file_path):
            #     with open(file_path, 'r', encoding='utf-8') as f:
            #         return f.read()
            return ""  # Заглушка
        except Exception as e:
            logger.error(f"Ошибка при получении YAML для правила {rule_id}: {str(e)}")
            return ""

    def get_rule_metadata_by_id(self, rule_id: str) -> Dict[str, Any]:
        """
        Получает метаданные правила по его ID напрямую из векторной БД.
        Полезно для предварительного просмотра правила перед его доработкой.
        
        Args:
            rule_id (str): ID правила.
            
        Returns:
            Dict[str, Any]: Метаданные правила или пустой словарь, если правило не найдено.
        """
        try:
            # Пытаемся получить правило по его ID
            results = self.collection.get(
                ids=[rule_id],
                include=['metadatas', 'documents']
            )
            
            if results['ids']:
                metadata = results['metadatas'][0]
                # ChromaDB может возвращать список для одного элемента
                if isinstance(metadata, list):
                    metadata = metadata[0]
                return metadata
            else:
                logger.warning(f"Правило с ID {rule_id} не найдено в векторной БД")
                return {}
                
        except Exception as e:
            logger.error(f"Ошибка при получении метаданных для правила {rule_id}: {str(e)}")
            return {}

    def search_rules_by_keyword(self, query_text: str, n_results: int = 10) -> List[Dict]:
        """
        Выполняет гибридный поиск: семантический + по ключевым словам.
        Улучшает релевантность поиска для интерактивного выбора.
        
        Args:
            query_text (str): Текст запроса.
            n_results (int): Количество возвращаемых результатов.
            
        Returns:
            List[Dict]: Список с результатами поиска.
        """
        try:
            # Семантический поиск (уже реализован)
            semantic_results = self.query_rules(query_text, n_results)
            
            # Дополнительно можно добавить поиск по ключевым словам в метаданных
            # Это улучшит релевантность для коротких технических запросов
            
            return semantic_results
            
        except Exception as e:
            logger.error(f"Ошибка при гибридном поиске: {str(e)}")
            return []

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику коллекции для мониторинга и отладки.
        
        Returns:
            Dict[str, Any]: Статистика коллекции.
        """
        try:
            count = self.collection.count()
            return {
                "total_rules": count,
                "persist_directory": self.persist_directory,
                "collection_name": "semgrep_rules"
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики коллекции: {str(e)}")
            return {"total_rules": 0, "error": str(e)}
    def __init__(self, persist_directory: str = "./data/vector_db"):
        self.persist_directory = persist_directory
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Инициализация клиента ChromaDB
        self.chroma_client = chromadb.Client(
            Settings(
                persist_directory=persist_directory,
                is_persistent=True,
            )
        )
        
        # Создание или получение коллекции
        self.collection = self.chroma_client.get_or_create_collection(
            name="semgrep_rules",
            metadata={"hnsw:space": "cosine"} # Используем косинусное расстояние для схожести
        )
        logger.info("Инициализирован менеджер векторной БД")

    def load_and_process_rules(self, rules_directory: str) -> List[Dict[str, Any]]:
        """
        Загружает и обрабатывает все YAML файлы правил из указанной директории.
        Рекурсивно обрабатывает поддиректории.
        """
        processed_rules = []
        
        if not os.path.exists(rules_directory):
            raise FileNotFoundError(f"Директория с правилами не найдена: {rules_directory}")
        
        # Рекурсивно ищем все YAML файлы
        yaml_files = []
        for root, dirs, files in os.walk(rules_directory):
            for filename in files:
                if filename.endswith(('.yaml', '.yml')):
                    yaml_files.append(os.path.join(root, filename))
        
        for filepath in yaml_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    rule_data = yaml.safe_load(file)
                    
                    # Пропускаем файлы без правил
                    if not rule_data or 'rules' not in rule_data:
                        continue
                    
                    # Извлекаем информацию о каждом правиле в файле
                    for rule in rule_data.get('rules', []):
                        rule_id = rule.get('id', '')
                        rule_message = rule.get('message', '')
                        rule_severity = rule.get('severity', '')
                        rule_languages = rule.get('languages', [])
                        
                        # Извлекаем метаданные для улучшения поиска
                        metadata = rule.get('metadata', {})
                        rule_category = metadata.get('category', '')
                        rule_technology = metadata.get('technology', [])
                        rule_cwe = metadata.get('cwe', [])
                        
                        # Создаем объединенный текст для эмбеддинга
                        combined_text = f"""
                        ID: {rule_id}
                        Message: {rule_message}
                        Severity: {rule_severity}
                        Languages: {rule_languages}
                        Category: {rule_category}
                        Technology: {rule_technology}
                        CWE: {rule_cwe}
                        """
                        
                        processed_rules.append({
                            'id': rule_id,
                            'message': rule_message,
                            'severity': rule_severity,
                            'languages': rule_languages,
                            'category': rule_category,
                            'technology': rule_technology,
                            'cwe': rule_cwe,
                            'combined_text': combined_text,
                            'source_file': os.path.relpath(filepath, rules_directory)
                        })
                        
            except Exception as e:
                logger.error(f"Ошибка при обработке файла {filepath}: {str(e)}")
                continue
        
        logger.info(f"Успешно обработано {len(processed_rules)} правил из {len(yaml_files)} файлов")
        return processed_rules

    def build_vector_db(self, rules_directory: str):
        """
        Основной метод для построения векторной базы данных из правил.
        
        Args:
            rules_directory (str): Путь к директории с правилами Semgrep
        """
        # Загружаем и обрабатываем правила
        rules = self.load_and_process_rules(rules_directory)
        
        if not rules:
            logger.warning("Не найдено правил для обработки. Векторная БД не будет создана.")
            return
        
        # Подготавливаем данные для добавления в коллекцию
        ids = []
        documents = []
        metadatas = []
        
        for rule in rules:
            ids.append(rule['id'])
            documents.append(rule['combined_text'])
            metadatas.append({
                'source_file': rule['source_file'],
                'severity': rule['severity'],
                'languages': str(rule['languages']),
                'message': rule['message']
            })
        
        # Генерируем эмбеддинги
        logger.info("Генерация эмбеддингов для правил...")
        embeddings = self.embedder.encode(documents).tolist()
        
        # Добавляем данные в коллекцию
        logger.info("Добавление данных в векторную БД...")
        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        # Сохраняем БД на диск
        self.chroma_client.persist()
        logger.info(f"Векторная БД успешно построена и сохранена в {self.persist_directory}")
        logger.info(f"Добавлено {len(ids)} правил")

    def query_rules(self, query_text: str, n_results: int = 5) -> List[Dict]:
        """
        Выполняет семантический поиск по векторной БД правил.
        
        Args:
            query_text (str): Текст запроса (описание уязвимости)
            n_results (int): Количество возвращаемых результатов
            
        Returns:
            List[Dict]: Список с результатами поиска
        """
        # Генерируем эмбеддинг для запроса
        query_embedding = self.embedder.encode([query_text]).tolist()
        
        # Выполняем запрос к коллекции
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Форматируем результаты
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'id': results['ids'][0][i],
                'distance': results['distances'][0][i],
                'metadata': results['metadatas'][0][i],
                'document': results['documents'][0][i]
            })
        
        logger.info(f"Найдено {len(formatted_results)} результатов для запроса: '{query_text}'")
        return formatted_results

# Функция для простого использования класса
def build_vector_db_from_rules(rules_dir: str = "./data/raw_rules"):
    """
    Утилитарная функция для быстрого построения векторной БД из правил.
    
    Args:
        rules_dir (str): Путь к директории с правилами Semgrep
    """
    db_manager = VectorDBManager()
    db_manager.build_vector_db(rules_dir)

if __name__ == "__main__":
    # Если скрипт запущен напрямую, построим БД
    build_vector_db_from_rules()