import subprocess
import tempfile
import os
import json
import logging
from typing import Dict, Any, List, Optional

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SemgrepRunner:
    """
    Класс для запуска Semgrep CLI и анализа результатов.
    """
    
    def __init__(self):
        """Проверяет, установлен ли Semgrep CLI."""
        try:
            result = subprocess.run(["semgrep", "--version"], 
                                  capture_output=True, text=True, check=True)
            self.semgrep_available = True
            logger.info(f"Semgrep CLI доступен: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.semgrep_available = False
            logger.error("Semgrep CLI не установлен или не доступен в PATH")

    def run_semgrep(self, rule_content: str, test_code: str, 
                   language: str = "python") -> Dict[str, Any]:
        """
        Запускает Semgrep для проверки правила на тестовом коде.
        
        Args:
            rule_content: YAML-содержимое правила Semgrep
            test_code: Код для тестирования
            language: Язык программирования тестового кода
            
        Returns:
            Словарь с результатами выполнения Semgrep
        """
        if not self.semgrep_available:
            return {
                "success": False,
                "error": "Semgrep CLI не доступен",
                "results": []
            }
        
        try:
            # Создаем временные файлы для правила и тестового кода
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as rule_file:
                rule_file.write(rule_content)
                rule_path = rule_file.name
            
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{language}', delete=False) as code_file:
                code_file.write(test_code)
                code_path = code_file.name
            
            # Запускаем Semgrep
            cmd = [
                "semgrep", 
                "--config", rule_path,
                "--json",
                code_path
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30  # Таймаут 30 секунд
            )
            
            # Удаляем временные файлы
            os.unlink(rule_path)
            os.unlink(code_path)
            
            if result.returncode == 0:
                # Парсим JSON вывод
                output = json.loads(result.stdout)
                
                return {
                    "success": True,
                    "results": output.get("results", []),
                    "errors": output.get("errors", []),
                    "stats": output.get("stats", {})
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr,
                    "results": [],
                    "errors": []
                }
                
        except subprocess.TimeoutExpired:
            logger.error("Semgrep выполнение превысило таймаут")
            return {
                "success": False,
                "error": "Таймаут выполнения",
                "results": []
            }
        except json.JSONDecodeError:
            logger.error("Не удалось распарсить JSON вывод Semgrep")
            return {
                "success": False,
                "error": "Невалидный JSON вывод",
                "results": []
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка при выполнении Semgrep: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

    def validate_rule(self, rule_content: str, positive_test: str, 
                     negative_test: str, language: str = "python") -> Dict[str, Any]:
        """
        Полная валидация правила на позитивных и негативных тестах.
        
        Args:
            rule_content: YAML-содержимое правила Semgrep
            positive_test: Код с уязвимостью (должен обнаруживаться)
            negative_test: Код без уязвимости (не должен обнаруживаться)
            language: Язык программирования тестового кода
            
        Returns:
            Словарь с результатами валидации
        """
        # Тестируем на позитивном примере
        positive_result = self.run_semgrep(rule_content, positive_test, language)
        
        # Тестируем на негативном примере
        negative_result = self.run_semgrep(rule_content, negative_test, language)
        
        # Анализируем результаты
        validation_passed = (
            positive_result["success"] and 
            negative_result["success"] and
            len(positive_result["results"]) > 0 and  # Обнаружена уязвимость
            len(negative_result["results"]) == 0     # Нет ложных срабатываний
        )
        
        return {
            "validation_passed": validation_passed,
            "positive_test": positive_result,
            "negative_test": negative_result,
            "details": {
                "positive_detected": len(positive_result["results"]) > 0,
                "negative_detected": len(negative_result["results"]) > 0,
                "errors": positive_result.get("errors", []) + negative_result.get("errors", [])
            }
        }