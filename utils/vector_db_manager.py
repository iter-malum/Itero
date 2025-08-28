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
        
        Args:
            rules_directory (str): Путь к директории с правилами Semgrep (.yaml/.yml файлы)
            
        Returns:
            List[Dict]: Список словарей с данными каждого правила
        """
        processed_rules = []
        
        if not os.path.exists(rules_directory):
            raise FileNotFoundError(f"Директория с правилами не найдена: {rules_directory}")
        
        for filename in os.listdir(rules_directory):
            if filename.endswith(('.yaml', '.yml')):
                filepath = os.path.join(rules_directory, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as file:
                        rule_data = yaml.safe_load(file)
                        
                        # Извлекаем информацию о каждом правиле в файле
                        for rule in rule_data.get('rules', []):
                            rule_id = rule.get('id', '')
                            rule_message = rule.get('message', '')
                            rule_severity = rule.get('severity', '')
                            rule_languages = rule.get('languages', [])
                            rule_patterns = str(rule.get('patterns', []))
                            
                            # Создаем объединенный текст для эмбеддинга
                            combined_text = f"""
                            ID: {rule_id}
                            Message: {rule_message}
                            Severity: {rule_severity}
                            Languages: {rule_languages}
                            Patterns: {rule_patterns}
                            """
                            
                            processed_rules.append({
                                'id': rule_id,
                                'message': rule_message,
                                'severity': rule_severity,
                                'languages': rule_languages,
                                'patterns': rule_patterns,
                                'combined_text': combined_text,
                                'source_file': filename
                            })
                            
                except Exception as e:
                    logger.error(f"Ошибка при обработке файла {filename}: {str(e)}")
                    continue
        
        logger.info(f"Успешно обработано {len(processed_rules)} правил из директории {rules_directory}")
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