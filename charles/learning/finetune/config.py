from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FineTuneDatasetConfig(BaseModel):
    dataset_id: str
    dataset_version: str
    dataset_format: Literal["chat", "instruction"] = "chat"
    source_train_path: str
    source_eval_path: str | None = None
    prepared_train_path: str
    prepared_eval_path: str | None = None
    export_summary_path: str | None = None


class FineTuneModelConfig(BaseModel):
    base_model_path: str = Field(
        ...,
        description="Path to local Transformers-compatible weights. Ollama tags alone are not trainable inputs.",
    )
    tokenizer_path: str | None = None
    ollama_target_tag: str = "meditron:7b"
    model_family: Literal["llama_like"] = "llama_like"
    trust_remote_code: bool = False


class FineTuneLoRAConfig(BaseModel):
    r: int = Field(default=16, ge=1)
    alpha: int = Field(default=32, ge=1)
    dropout: float = Field(default=0.05, ge=0.0, le=0.5)
    bias: Literal["none", "all", "lora_only"] = "none"
    target_modules: list[str] = Field(
        default_factory=lambda: [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    )


class FineTuneQuantizationConfig(BaseModel):
    enabled: bool = True
    load_in_4bit: bool = True
    quant_type: Literal["nf4", "fp4"] = "nf4"
    compute_dtype: Literal["bfloat16", "float16", "float32"] = "bfloat16"
    use_double_quant: bool = True


class FineTuneTrainingConfig(BaseModel):
    max_seq_length: int = Field(default=2048, ge=128)
    learning_rate: float = Field(default=1e-4, gt=0)
    num_train_epochs: float = Field(default=2.0, gt=0)
    per_device_train_batch_size: int = Field(default=1, ge=1)
    per_device_eval_batch_size: int = Field(default=1, ge=1)
    gradient_accumulation_steps: int = Field(default=8, ge=1)
    warmup_ratio: float = Field(default=0.03, ge=0.0, le=1.0)
    weight_decay: float = Field(default=0.0, ge=0.0)
    logging_steps: int = Field(default=10, ge=1)
    save_steps: int = Field(default=50, ge=1)
    eval_steps: int = Field(default=50, ge=1)
    save_total_limit: int = Field(default=2, ge=1)
    gradient_checkpointing: bool = True
    packing: bool = False
    seed: int = 42
    optim: str = "paged_adamw_8bit"
    lr_scheduler_type: str = "cosine"


class FineTuneArtifactsConfig(BaseModel):
    run_dir: str
    output_dir: str
    logging_dir: str
    adapter_output_dir: str
    environment_report_path: str
    training_summary_path: str


class FineTuneRunConfig(BaseModel):
    run_id: str
    created_at: str
    training_stage: str = "step3_local_sft_scaffold"
    python_executable: str | None = None
    dataset: FineTuneDatasetConfig
    model: FineTuneModelConfig
    lora: FineTuneLoRAConfig = Field(default_factory=FineTuneLoRAConfig)
    quantization: FineTuneQuantizationConfig = Field(default_factory=FineTuneQuantizationConfig)
    training: FineTuneTrainingConfig = Field(default_factory=FineTuneTrainingConfig)
    artifacts: FineTuneArtifactsConfig
    notes: list[str] = Field(default_factory=list)

    @field_validator("notes", mode="before")
    @classmethod
    def _normalize_notes(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]
