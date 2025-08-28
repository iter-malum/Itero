#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.vector_db_manager import VectorDBManager

def test_search():
    db_manager = VectorDBManager()
    
    # Тестовые запросы
    test_queries = [
        "SQL injection vulnerability",
        "XSS cross site scripting",
        "hard coded password"
    ]
    
    for query in test_queries:
        print(f"\n=== Результаты для запроса: '{query}' ===")
        results = db_manager.query_rules(query, n_results=3)
        
        for i, result in enumerate(results):
            print(f"\n{i+1}. ID: {result['id']}")
            print(f"   Distance: {result['distance']:.4f}")
            print(f"   Message: {result['metadata']['message']}")
            print(f"   Source: {result['metadata']['source_file']}")

if __name__ == "__main__":
    test_search()