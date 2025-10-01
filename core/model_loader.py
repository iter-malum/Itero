# core/model_loader.py

from peft import PeftModel
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

def load_peft_model_simple(base_model_name, lora_adapters_path):
    """
    Упрощенная загрузка модели без автоматического оффлоуда.
    """
    # Пытаемся загрузить на GPU, если не получится — на CPU
    if torch.cuda.is_available():
        device = "cuda"
        print(f"✅ Используется GPU: {torch.cuda.get_device_name()}")
    else:
        device = "cpu"
        print("⚠️  GPU не обнаружен, используется CPU.")

    # Загрузка токенизатора и базовой модели
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    
    # Пробуем загрузить модель на одно устройство
    try:
        model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=torch.float16,
            device_map=device,  # Пробуем загрузить всё на одно устройство
            # offload_folder="./offload",  # Закомментируем оффлоуд
            # offload_state_dict=False,    # Закомментируем оффлоуд
        )
    except RuntimeError as e:
        # Если не хватило памяти, попробуем загрузить на CPU (медленно, но для теста)
        if "out of memory" in str(e).lower():
            print("⚠️  Не хватило памяти на GPU, пробуем загрузить на CPU.")
            model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                torch_dtype=torch.float16,
                device_map="cpu",
            )
        else:
            raise e
    
    # Загрузка LoRA-адаптеров
    model = PeftModel.from_pretrained(model, lora_adapters_path)
    
    return model, tokenizer

# Для теста используйте эту функцию
if __name__ == "__main__":
    model, tokenizer = load_peft_model_simple(
        "codellama/CodeLlama-7b-hf",
        "outputs/codeLlama-7b-semgrep-lora"
    )
    print("✅ Модель загружена в упрощенном режиме!")