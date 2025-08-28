# Itero 🛠️

Itero is a multi-agent LLM system designed to automate the creation and updating of static code analysis rules for Semgrep. By describing a vulnerability in natural language, Itero intelligently searches for existing patterns, crafts new precise rules, and validates them against your code—dramatically reducing the manual effort required for security tooling maintenance.

## Key Features

*   **🤖 Multi-Agent Architecture:** Leverages Microsoft's AutoGen to orchestrate specialized AI agents for analysis, search, engineering, and validation.
*   **🔍 Semantic Rule Search:** Utilizes RAG (Retrieval-Augmented Generation) with ChromaDB to find relevant existing rules from your codebase.
*   **✍️ Intelligent Rule Generation:** Empowers a local LLM (via Ollama) to write and update high-quality Semgrep YAML rules based on natural language descriptions and code examples.
*   **✅ Integrated Validation:** Automatically tests generated rules using the Semgrep CLI to ensure they trigger correctly and avoid false positives.
*   **💻 Developer-Centric:** Designed as a local-first prototype, giving you full control over your code and data without relying on external APIs.

## Верхнеуровневая архитектура проекта (Component Diagram)

Веб-интерфейс и Бэкенд обведены пунктиром как будущие компоненты.
Ядро системы — это основной модуль, который вы разрабатываете сейчас.
Агенты общаются друг с другом через механизм Group Chat от AutoGen.
Агенты взаимодействуют с утилитами (кэш, менеджер БД, Semgrep Runner) через механизм Function Call (агент говорит, что ему нужна функция, и User Proxy Agent ее выполняет).
Утилиты работают с низкоуровневыми компонентами: файловой системой (логи, БД) и системными вызовами (Semgrep CLI).
Локальная LLM (Ollama) работает как отдельный сервис, к которому все агенты обращаются по API.

+-------------------------------------------------------------------------------------------+
|                                  Локальная машина разработчика                             |
|                                                                                            |
|  +-----------------------------+  HTTP/API       +------------------------------------+    |
|  |         Веб-интерфейс       | <-------------> |          Бэкенд (FastAPI)          |    |
|  |       (React/Next.js)       |    (Future)     |            (Future)                |    |
|  +-----------------------------+                 +------------------------------------+    |
|                                                                                            |
|  +-------------------------------------------------------------------------------------+   |
|  |                              Ядро системы (Python)                                  |   |
|  |                                                                                     |   |
|  |  +-----------+  AutoGen   +-------------+  AutoGen   +-------------+                |   |
|  |  |   Агент-  | <--------> |   Агент-    | <--------> |   Агент-    |                |   |
|  |  |Координатор|   Group    |  Поисковик  |   Chat     | Инженер     |                |   |
|  |  | (Manager) |   Chat     | (Search)    |            | (RuleEngine)|                |   |
|  |  +-----------+            +-------------+            +-------------+                |   |
|  |      | ^                      | ^                         | ^                       |   |
|  |      | | Function Call        | | Function Call           | | Function Call         |   |
|  |      v |                      v |                         v |                       |   |
|  |  +-----------+            +-----------------------------------+   +-------------+   |   |
|  |  |   Кэш     |            |   Менеджер Векторной Базы Данных  |   | Semgrep     |   |   |
|  |  | (Cache)   |            |        (Vector DB Manager)        |   | Runner      |   |   |
|  |  +-----------+            +-----------------------------------+   +-------------+   |   |
|  |                                                                                     |   |
|  +-------------------------------------------------------------------------------------+   |
|           |                              |                              |                  |
|           | Read/Write                   | Read/Write                   | Execute          |
|           v                              v                              v                  |
|  +-------------------+        +------------------------+        +---------------------+    |
|  |    Логи (logs/)   |        |  Векторная БД (Chroma) |        | Semgrep CLI (Binary)|    |
|  |    (Text files)   |        |   (data/vector_db/)    |        |   (System Level)    |    |
|  +-------------------+        +------------------------+        +---------------------+    |
|                                                                                            |
|  +--------------------------------------------------------------------------------------+  |
|  |                              Внешние сервисы (Ollama)                                |  |
|  |                                                                                      |  |
|  |  +-----------------------------------------------------------------------------+     |  |
|  |  |                   Локальная LLM (deepseek-coder:6.7b)                       |     |  |
|  |  |                 (HTTP API на http://localhost:11434)                        |     |  |
|  |  +-----------------------------------------------------------------------------+     |  |
|  +-------------------------------------------------------------------------------------+   |
|                                                                                            |
+-------------------------------------------------------------------------------------------+

## Ключевые потоки данных:

### Поток поиска:

[Data] Текстовое описание уязвимости -> Агент-Координатор -> Агент-Поисковик
[Function Call] Агент-Поисковик -> Vector DB Manager -> [Query] -> ChromaDB
[Data] ChromaDB -> [JSON Results] -> Vector DB Manager -> Агент-Поисковик -> Агент-Координатор

### Поток генерации:

[Data] Исходный код + описание + (опционально найденные правила) -> Агент-Координатор -> Агент-Инженер
[Function Call] Агент-Инженер формирует промпт -> [HTTP Request] -> Ollama API
[Data] Ollama API -> [Generated Text] -> Агент-Инженер (пытается извлечь YAML)
[Data] Сгенерированный YAML -> Агент-Инженер -> Агент-Координатор

### Поток валидации:

[Data] Сгенерированный YAML + Исходный код -> Агент-Координатор -> Агент-Валидатор
[Function Call] Агент-Валидатор -> Semgrep Runner -> [System Call] -> Semgrep CLI
[Data] Semgrep CLI -> [Stdout/Stderr] -> Semgrep Runner (парсит JSON)
[Data] Результат парсинга (успех/ошибка) -> Агент-Валидатор -> Агент-Координатор
