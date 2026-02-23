# Prompt Templates

This directory contains all prompt templates used by the MarketingAgent system.

## How It Works

Instead of hardcoding prompts with f-strings in the code, prompts are stored as template files with placeholders in the format `{variable_name}`. These are loaded and formatted at runtime using the `load_prompt()` function.

### Benefits
- ✅ Easy to version control and compare prompt changes
- ✅ Allows collaboration with non-technical team members
- ✅ Supports A/B testing different prompt versions
- ✅ Cleaner code separation (logic vs prompts)

## Usage

```python
from utils.prompt_loader import load_prompt

# Load and format a prompt template
prompt = load_prompt(
    "data_analysis_prompt",
    campaign_type="Product Launch",
    target_industry="Technology"
)
```

## Sample Prompt Inputs

- `data_analysis_prompt.txt` - For analyzing historical campaign data
  - Variables: `campaign_type`, `target_industry`
  
- `market_research_prompt.txt` - For synthesizing web search results
  - Variables: `campaign_type`, `target_industry`, `search_results`
  
- `strategy_generation_prompt.txt` - For generating high-level campaign strategy
  - Variables: `data_insights`, `market_trends`, `campaign_type`, `target_industry`, `budget`, `timeline`, `goals`

## Template Syntax

Use curly braces for variable placeholders:
```
Your campaign type is {campaign_type} targeting {target_industry}.
Budget: {budget}
```

Then format with:
```python
load_prompt("template_name", campaign_type="Launch", target_industry="Tech", budget="$100k")
```
