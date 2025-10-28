import json
import torch
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer, 
    BitsAndBytesConfig,
    TrainingArguments,
    DataCollatorForSeq2Seq
)
from peft import LoraConfig, get_peft_model, PeftModel
from trl import SFTTrainer
import datasets
from datetime import datetime
import os

def load_and_prepare_data(train_path, val_path):
    """Загрузка и подготовка данных в правильном формате"""
    
    with open(train_path, 'r', encoding='utf-8') as f:
        train_data = json.load(f)
    with open(val_path, 'r', encoding='utf-8') as f:
        val_data = json.load(f)
    
    print(f"Загружено {len(train_data)} обучающих и {len(val_data)} валидационных примеров")
    
    # Преобразуем в формат для языковой модели
    def format_for_training(examples):
        formatted_texts = []
        for i in range(len(examples)):
            instruction = examples[i]["instruction"]
            input_text = examples[i]["input"]
            output = examples[i]["output"]
            
            # Форматируем в стиле инструктивной модели
            formatted = f"""<s>[INST] {instruction}

{input_text} [/INST] {output}</s>"""
            formatted_texts.append(formatted)
        
        return {"text": formatted_texts}
    
    train_dataset = datasets.Dataset.from_list(train_data)
    val_dataset = datasets.Dataset.from_list(val_data)
    
    train_dataset = train_dataset.map(format_for_training, batched=True)
    val_dataset = val_dataset.map(format_for_training, batched=True)
    
    return train_dataset, val_dataset

def setup_model_and_tokenizer(model_name="codellama/CodeLlama-7B-Instruct-hf"):
    """Настройка модели и токенизатора"""
    
    # Конфигурация квантизации для RTX 5070 (12GB)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,  # Двойное квантование для лучшего качества
    )
    
    # Загрузка токенизатора
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    # Загрузка модели
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        use_cache=False,  # Важно для gradient checkpointing
    )
    
    return model, tokenizer

def setup_lora_config():
    """Конфигурация LoRA для семантики Semgrep"""
    
    return LoraConfig(
        r=16,  # Rank - хороший баланс между качеством и скоростью
        lora_alpha=32,
        target_modules=[
            "q_proj", "v_proj", "k_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj"  # Для полного покрытия MLP
        ],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        # Увеличиваем ранг для лучшего понимания структуры YAML
        modules_to_save=None,
    )

def main():
    # Конфигурация
    MODEL_NAME = "codellama/CodeLlama-7B-Instruct-hf"
    TRAIN_DATA_PATH = "semgrep_prepared_data/train_data.json"
    VAL_DATA_PATH = "semgrep_prepared_data/val_data.json"
    OUTPUT_DIR = f"semgrep-finetuned-{datetime.now().strftime('%Y%m%d-%H%M')}"
    
    print("🚀 Начало дообучения модели для генерации правил Semgrep...")
    
    # 1. Загрузка и подготовка данных
    print("📊 Загрузка данных...")
    train_dataset, val_dataset = load_and_prepare_data(TRAIN_DATA_PATH, VAL_DATA_PATH)
    
    # 2. Настройка модели и токенизатора
    print("🤖 Загрузка модели и токенизатора...")
    model, tokenizer = setup_model_and_tokenizer(MODEL_NAME)
    
    # 3. Настройка LoRA
    print("🎛️ Настройка LoRA...")
    lora_config = setup_lora_config()
    model = get_peft_model(model, lora_config)
    
    # 4. Параметры обучения, оптимизированные для генерации YAML
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        overwrite_output_dir=True,
        
        # Параметры батчей для RTX 5070
        per_device_train_batch_size=2,  # Оптимально для 12GB
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=4,  # Эффективный batch size = 8
        dataloader_pin_memory=False,
        
        # Оптимизация обучения
        num_train_epochs=4,  # Увеличиваем для лучшего понимания синтаксиса
        learning_rate=1.5e-4,  # Немного ниже для стабильности
        warmup_steps=100,
        optim="paged_adamw_8bit",
        
        # Регуляризация
        weight_decay=0.01,
        max_grad_norm=0.3,
        
        # Сохранение и логирование
        logging_dir=f"{OUTPUT_DIR}/logs",
        logging_steps=50,
        save_steps=500,
        evaluation_strategy="steps",
        eval_steps=200,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        
        # FP16 для экономии памяти
        fp16=True,
        
        # Gradient checkpointing для экономии памяти
        gradient_checkpointing=True,
        
        # Прогресс
        report_to=["tensorboard"],
        run_name=f"semgrep-finetune-{datetime.now().strftime('%Y%m%d-%H%M')}",
    )
    
    # 5. Создание тренера с учетом специфики Semgrep
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        dataset_text_field="text",
        tokenizer=tokenizer,
        max_seq_length=3072,  # Увеличиваем для длинных правил Semgrep
        packing=False,  # Не упаковываем для лучшего обучения
        data_collator=DataCollatorForSeq2Seq(
            tokenizer,
            pad_to_multiple_of=8,
            return_tensors="pt",
            padding=True,
        ),
    )
    
    # 6. Запуск обучения
    print("🎯 Начало обучения...")
    train_result = trainer.train()
    
    # 7. Сохранение результатов
    print("💾 Сохранение модели...")
    
    # Сохраняем адаптеры LoRA
    trainer.model.save_pretrained(f"{OUTPUT_DIR}/lora-adapters")
    tokenizer.save_pretrained(f"{OUTPUT_DIR}/lora-adapters")
    
    # Сохраняем метрики
    with open(f"{OUTPUT_DIR}/training_metrics.json", "w") as f:
        json.dump(train_result.metrics, f, indent=2)
    
    print(f"✅ Обучение завершено! Результаты сохранены в: {OUTPUT_DIR}")
    
    return trainer

def test_trained_model(model_path, tokenizer_path):
    """Тестирование обученной модели"""
    
    print("\n🧪 Тестирование обученной модели...")
    
    # Загрузка базовой модели
    base_model = AutoModelForCausalLM.from_pretrained(
        "codellama/CodeLlama-7B-Instruct-hf",
        device_map="auto",
        torch_dtype=torch.float16,
    )
    
    # Загрузка адаптеров
    model = PeftModel.from_pretrained(base_model, model_path)
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
    
    # Тестовые промпты
    test_prompts = [
        """Напиши правило Semgrep для обнаружения SQL injection в Python""",
        
        """Создай правило Semgrep для поиска hardcoded API keys в JavaScript""",
        
        """Доработай правило для обнаружения XSS в веб-приложениях на Java"""
    ]
    
    for i, prompt in enumerate(test_prompts):
        print(f"\n📝 Тест {i+1}: {prompt}")
        
        # Форматируем промпт
        formatted_prompt = f"<s>[INST] {prompt} [/INST]"
        
        # Генерация
        inputs = tokenizer(formatted_prompt, return_tensors="pt").to("cuda")
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.1
            )
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"🤖 Ответ модели:\n{response}")

if __name__ == "__main__":
    # Запуск обучения
    trainer = main()
    
    # Тестирование (опционально)
    # test_trained_model("semgrep-finetuned/lora-adapters", "semgrep-finetuned/lora-adapters")