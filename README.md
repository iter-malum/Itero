# Itero 🛠️

Itero is a multi-agent LLM system designed to automate the creation and updating of static code analysis rules for Semgrep. By describing a vulnerability in natural language, Itero intelligently searches for existing patterns, crafts new precise rules, and validates them against your code—dramatically reducing the manual effort required for security tooling maintenance.

## Key Features

*   **🤖 Multi-Agent Architecture:** Leverages Microsoft's AutoGen to orchestrate specialized AI agents for analysis, search, engineering, and validation.
*   **🔍 Semantic Rule Search:** Utilizes RAG (Retrieval-Augmented Generation) with ChromaDB to find relevant existing rules from your codebase.
*   **✍️ Intelligent Rule Generation:** Empowers a local LLM (via Ollama) to write and update high-quality Semgrep YAML rules based on natural language descriptions and code examples.
*   **✅ Integrated Validation:** Automatically tests generated rules using the Semgrep CLI to ensure they trigger correctly and avoid false positives.
*   **💻 Developer-Centric:** Designed as a local-first prototype, giving you full control over your code and data without relying on external APIs.

## Architecture Overview

RuleSmith is built on a robust agent-based workflow:

