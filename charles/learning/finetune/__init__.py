"""Local fine-tuning helpers and schemas for CHARLES."""

from .config import FineTuneRunConfig
from .evaluation import (
    aggregate_record_metrics,
    comparison_delta,
    extract_first_json_object,
    load_evaluation_targets,
    score_prediction,
)
from .runtime import inspect_run_environment, prepare_text_samples, write_prepared_text_dataset
from .schemas import FineTuneChatSample, FineTuneInstructionSample, PreparedTextSample

__all__ = [
    "FineTuneRunConfig",
    "FineTuneChatSample",
    "FineTuneInstructionSample",
    "PreparedTextSample",
    "prepare_text_samples",
    "write_prepared_text_dataset",
    "inspect_run_environment",
    "extract_first_json_object",
    "load_evaluation_targets",
    "score_prediction",
    "aggregate_record_metrics",
    "comparison_delta",
]
