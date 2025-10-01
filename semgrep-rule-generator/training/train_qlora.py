#!/usr/bin/env python3
"""
Скрипт для обучения модели с использованием QLoRA
Специально адаптирован для генерации правил Semgrep
"""
import os
import torch
import yaml
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset
import json
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_training(config_path):
    """Настраивает обучение на основе конфигурационного файла"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)  # ИСПОЛЬЗУЕМ YAML вместо JSON
    
    if config is None:
        logger.error(f"Конфигурационный файл {config_path} пустой или содержит невалидный YAML")
        raise ValueError("Конфигурационный файл не может быть пустым")
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=config["load_in_4bit"],
        bnb_4bit_quant_type=config["bnb_4bit_quant_type"],
        bnb_4bit_compute_dtype=getattr(torch, config["bnb_4bit_compute_dtype"]),
        bnb_4bit_use_double_quant=config["bnb_4bit_use_double_quant"],
    )
    
    # Загрузка модели и токенизатора
    logger.info(f"Загружаем модель: {config['model_name']}")
    model = AutoModelForCausalLM.from_pretrained(
        config["model_name"],
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    # Подготовка модели для обучения
    model = prepare_model_for_kbit_training(model)
    
    # Настройка LoRA
    lora_config = LoraConfig(
        r=config["lora_r"],
        lora_alpha=config["lora_alpha"],
        target_modules=config["lora_target_modules"],
        lora_dropout=config["lora_dropout"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # Загрузка данных
    logger.info(f"Загружаем данные из: {config['dataset_name']}")
    dataset = load_dataset('json', data_files={'train': config['dataset_name']})
    
    # Токенизация данных с учетом формата инструкций
    def tokenize_function(examples):
        # Создаем тексты в формате инструкций
        texts = []
        for prompt, completion in zip(examples['prompt'], examples['completion']):
            # Форматируем в стиле инструкции
            instruction_text = f"<s>[INST] Напиши правило Semgrep для обнаружения следующей проблемы:\n{prompt}\n[/INST]"
            full_text = instruction_text + completion + "</s>"
            texts.append(full_text)
        
        # Токенизируем
        tokenized = tokenizer(
            texts,
            truncation=True,
            max_length=config['max_seq_length'],
            padding=False
        )
        
        return tokenized
    
    tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=dataset["train"].column_names)
    
    # Настройка аргументов обучения
    training_args = TrainingArguments(
        output_dir=config["output_dir"],
        num_train_epochs=config["num_train_epochs"],
        per_device_train_batch_size=config["per_device_train_batch_size"],
        per_device_eval_batch_size=config["per_device_eval_batch_size"],
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        optim=config["optim"],
        learning_rate=float(config["learning_rate"]),
        weight_decay=config["weight_decay"],
        fp16=config["fp16"],
        tf32=config["tf32"],
        max_grad_norm=config["max_grad_norm"],
        max_steps=config["max_steps"],
        warmup_ratio=config["warmup_ratio"],
        lr_scheduler_type=config["lr_scheduler_type"],
        logging_dir=config["logging_dir"],
        logging_steps=config["logging_steps"],
        save_strategy=config["save_strategy"],
        save_total_limit=config["save_total_limit"],
        eval_strategy=config["eval_strategy"],
        eval_steps=config["eval_steps"],
        #predict_with_generation=config["predict_with_generation"],
        report_to="none",
        dataloader_pin_memory=False,
    )
    
    # Создаем коллатор данных
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )
    
    # Создаем тренер
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        eval_dataset=tokenized_dataset["train"].select(range(min(100, len(tokenized_dataset["train"])))),
        data_collator=data_collator,
    )
    
    return trainer, model, tokenizer, config

def main():
    """Основная функция обучения"""
    try:
        logger.info("=== Начало обучения ===")
        
        # Настраиваем обучение
        trainer, model, tokenizer, config = setup_training("training/config_qlora.yaml")
        
        # Запускаем обучение
        logger.info("Запускаем обучение...")
        train_result = trainer.train()
        
        # Сохраняем метрики
        metrics = train_result.metrics
        metrics_file = os.path.join(config["output_dir"], "training_metrics.json")
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
            
        # Сохраняем модель
        logger.info("Сохраняем модель...")
        trainer.save_model()
        tokenizer.save_pretrained(config["output_dir"])
        
        logger.info("=== Обучение завершено ===")
        logger.info(f"Метрики сохранены в: {metrics_file}")
        logger.info(f"Модель сохранена в: {config['output_dir']}")
        
    except Exception as e:
        logger.error(f"Ошибка во время обучения: {str(e)}")
        raise

if __name__ == "__main__":
    main()