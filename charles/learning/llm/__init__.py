"""Structured LLM dataset preparation for local CHARLES training."""

from .prompts import (
    INPUT_VARIANTS,
    PROMPT_ID,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_prompt_variants,
    build_reference_target,
    build_user_prompt,
    choose_split,
)
from .schemas import ExplanationTarget, LLMConversationMessage, LLMTrainingSample

__all__ = [
    "PROMPT_ID",
    "PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "INPUT_VARIANTS",
    "ExplanationTarget",
    "LLMConversationMessage",
    "LLMTrainingSample",
    "build_prompt_variants",
    "build_reference_target",
    "build_user_prompt",
    "choose_split",
]
