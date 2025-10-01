#!/usr/bin/env python3
import torch
import transformers
import bitsandbytes as bnb

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
print(f"Transformers version: {transformers.__version__}")
print(f"Bitsandbytes version: {bnb.__version__}")

# Проверка загрузки модели
from transformers import AutoModelForCausalLM, AutoTokenizer
model_name = "codellama/CodeLlama-7b-hf"
tokenizer = AutoTokenizer.from_pretrained(model_name)
print("✅ Токенизатор загружен успешно")

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    load_in_4bit=True,
    device_map="auto"
)
print("✅ Модель загружена успешно")