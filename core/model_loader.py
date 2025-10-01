# model_loader.py
from peft import PeftModel
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os

def load_peft_model(base_model_name, lora_adapters_path, offload_dir="./offload"):
    """Загружает базовую модель и дообученные LoRA-адаптеры с оффлоудом на CPU"""
    
    # Создаем директорию для оффлоуда, если не существует
    os.makedirs(offload_dir, exist_ok=True)
    
    # Загрузка токенизатора и базовой модели с правильными параметрами
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        device_map="auto",
        dtype=torch.float16,  # Используем dtype вместо torch_dtype :cite[2]:cite[5]:cite[8]
        offload_folder=offload_dir,  # Директория для оффлоуда на CPU
        offload_state_dict=True,     # Разрешить выгрузку state dict на CPU
    )
    
    # Загрузка LoRA-адаптеров с указанием offload_folder
    model = PeftModel.from_pretrained(
        model, 
        lora_adapters_path,
        offload_folder=offload_dir  # Критически важно для работы с большими моделями
    )
    
    return model, tokenizer

# Пример использования
if __name__ == "__main__":
    model, tokenizer = load_peft_model(
        "codellama/CodeLlama-7b-hf",
        "outputs/codeLlama-7b-semgrep-lora"
    )
    print("✅ Модель успешно загружена с оффлоудом на CPU")