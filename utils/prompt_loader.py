"""
Utility functions for loading and formatting prompt templates.
"""
import os
from pathlib import Path
from typing import Dict, Any


def get_prompts_dir() -> Path:
    """Get the absolute path to the prompts directory."""
    current_file = Path(__file__)
    project_root = current_file.parent.parent
    return project_root / "prompts"


def load_prompt(prompt_name: str, **kwargs: Any) -> str:
    """
    Load a prompt template from the prompts directory and format it with variables.
    
    Args:
        prompt_name: Name of the prompt file (without .txt extension)
        **kwargs: Variables to substitute in the template using {variable_name} syntax
        
    Returns:
        Formatted prompt string
        
    Example:
        >>> prompt = load_prompt(
        ...     "data_analysis_prompt",
        ...     campaign_type="Product Launch",
        ...     target_industry="Technology"
        ... )
    """
    prompts_dir = get_prompts_dir()
    prompt_file = prompts_dir / f"{prompt_name}.txt"
    
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    
    with open(prompt_file, 'r', encoding='utf-8') as f:
        template = f.read()
    
    try:
        # Use format() instead of f-strings for runtime variable substitution
        formatted_prompt = template.format(**kwargs)
        return formatted_prompt
    except KeyError as e:
        raise ValueError(f"Missing required variable in prompt template: {e}")


def list_available_prompts() -> list[str]:
    """List all available prompt templates."""
    prompts_dir = get_prompts_dir()
    if not prompts_dir.exists():
        return []
    
    return [f.stem for f in prompts_dir.glob("*.txt")]
