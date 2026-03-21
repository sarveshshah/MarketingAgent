"""LangGraph node functions — one function per graph node."""

import json
import sys
from datetime import datetime

import pandas as pd

from marketing_agent.config import settings, logger
from marketing_agent.models import (
    CampaignInput,
    CampaignStrategy,
    ChannelRecommendation,
    BudgetAllocation,
    RiskAssessment,
    GraphState,
)
from marketing_agent.llm import (
    _get_llm,
    load_prompt,
    _invoke_llm,
    _invoke_structured_llm,
    _extract_text,
)
from marketing_agent.agents import data_analysis_agent, search_agent


# ---------------------------------------------------------------------------
# Initial node: collect / validate campaign input
# ---------------------------------------------------------------------------

def collect_campaign_input(state: GraphState) -> dict:
    """Collect marketing campaign information from user."""

    if state.get("campaign_input"):
        return {}

    print("\n=== Marketing Campaign Input ===\n")

    campaign_input = {
        "campaign_type": input("Campaign type (e.g., product launch, brand awareness, retention): ").strip(),
        "target_industry": input("Target industry or market segment: ").strip(),
        "budget": input("Budget allocated for campaign: ").strip(),
        "timeline": input("Timeline for campaign (e.g., 3 months, Q1 2026): ").strip(),
        "goals": input("Specific goals or KPIs (comma-separated): ").strip(),
    }

    return {"campaign_input": CampaignInput(**campaign_input)}


# ---------------------------------------------------------------------------
# Data-analysis node
# ---------------------------------------------------------------------------

def analyze_past_campaigns(state: GraphState) -> dict:
    """Analyze past campaign data and return data-driven insights."""
    logger.info("Analyzing past campaign data...")
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before analyze_past_campaigns")

    try:
        df = pd.read_csv(settings.data_path)

        data_analysis_prompt = load_prompt(
            "data_analysis_prompt",
            campaign_type=campaign_input.campaign_type,
            target_industry=campaign_input.target_industry,
        )

        data_insights = data_analysis_agent(df, data_analysis_prompt)

    except FileNotFoundError:
        logger.warning("marketing_campaign_dataset.csv not found.")
        data_insights = "Historical data unavailable - dataset file not found."

    except Exception as e:
        logger.exception("Could not analyze data with agent.")
        data_insights = f"Data analysis unavailable due to error: {str(e)[:200]}"

    return {"past_campaign_insights": data_insights}


# ---------------------------------------------------------------------------
# Market-research node
# ---------------------------------------------------------------------------

def conduct_market_research(state: GraphState) -> dict:
    """Conduct market research by running search queries and synthesizing results."""

    logger.info("Conducting robust market research...")
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before conduct_market_research")

    # 1. Dynamically generate targeted search queries using an LLM
    search_queries_prompt = load_prompt(
        "generate_search_queries_prompt",
        campaign_type=campaign_input.campaign_type,
        target_industry=campaign_input.target_industry,
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
        goals=campaign_input.goals,
        current_year=datetime.now().year,
    )

    try:
        logger.info("Generating dynamic search queries...")
        queries_response = _invoke_llm(search_queries_prompt)
        content = _extract_text(
            queries_response.content if hasattr(queries_response, 'content') else queries_response
        )

        try:
            queries = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("[")
            end = content.rfind("]")
            if start == -1 or end == -1 or end <= start:
                raise ValueError("No JSON array found in LLM response")
            queries = json.loads(content[start : end + 1])

        if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
            raise ValueError("Parsed JSON is not a list of strings")

    except Exception as e:
        logger.warning(f"Failed to dynamically generate search queries: {e}. Falling back to default queries.")
        queries = [
            f"latest marketing trends for {campaign_input.campaign_type} in {campaign_input.target_industry} industry {datetime.now().year}",
            f"consumer behavior trends and preferences in {campaign_input.target_industry} {datetime.now().year}",
            f"successful marketing strategies for {campaign_input.campaign_type} targeting {campaign_input.target_industry}",
            f"emerging marketing channels and technologies for {campaign_input.target_industry}",
        ]

    # 2. Execute searches using the search agent
    search_results_text = search_agent(queries)

    # 3. Compile the results with an LLM
    logger.info("Synthesizing market trends from search results...")
    market_research_prompt = load_prompt(
        "market_research_prompt",
        campaign_type=campaign_input.campaign_type,
        target_industry=campaign_input.target_industry,
        search_results=search_results_text,
    )

    try:
        response = _invoke_llm(market_research_prompt)
        compiled_trends = _extract_text(
            response.content if hasattr(response, 'content') else response
        )
        logger.info("Successfully synthesized market trends.")
    except Exception as e:
        logger.error(f"Market research synthesis failed: {e}")
        compiled_trends = "Market trend synthesis failed. Raw data follows:\n\n" + search_results_text[:2000]

    return {"market_trends": compiled_trends}


# ---------------------------------------------------------------------------
# Shared LLM-fallback helper
# ---------------------------------------------------------------------------

def _llm_fallback(node_name: str, prompt: str, state_key: str, model_cls: type, fallback_fields: dict) -> dict:
    """Run the plain LLM (no structured output) as a last-resort fallback."""
    first_field = list(model_cls.model_fields)[0]
    logger.warning("Structured output failed for %s. Using text fallback.", node_name)
    try:
        response = _get_llm().invoke(prompt)
        content = str(response.content if hasattr(response, "content") else response)
        fields = {**fallback_fields, first_field: content[:500] + " ... (text fallback)"}
        return {state_key: model_cls(**fields)}
    except Exception as e:
        logger.error("Fallback text LLM also failed for %s: %s", node_name, e)
        return {state_key: model_cls(**fallback_fields)}


# ---------------------------------------------------------------------------
# Strategy generation node
# ---------------------------------------------------------------------------

def generate_strategy(state: GraphState) -> dict:
    """Generate a structured marketing strategy using data insights."""
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before generate_strategy")
    data_insights = state.get("past_campaign_insights", "")
    market_trends = state.get("market_trends", "")

    strategy_prompt = load_prompt(
        "strategy_generation_prompt",
        data_insights=data_insights,
        market_trends=market_trends,
        campaign_type=campaign_input.campaign_type,
        target_industry=campaign_input.target_industry,
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
        goals=campaign_input.goals,
    )

    try:
        strategy = _invoke_structured_llm(CampaignStrategy, strategy_prompt)
        return {"strategy": strategy}
    except Exception as e:
        logger.error(f"generate_strategy failed all retries: {e}. Executing fallback...")
        return _llm_fallback("generate_strategy", strategy_prompt, "strategy", CampaignStrategy,
                             {"target_audience": "N/A", "campaign_channels": "N/A",
                              "acquisition_cost_estimate": "N/A", "expected_roi": "N/A"})


# ---------------------------------------------------------------------------
# Channel recommendation node
# ---------------------------------------------------------------------------

def recommend_channels(state: GraphState) -> dict:
    """Recommend specific marketing channels based on data insights and campaign profile."""
    strategy = state.get("strategy")
    insights = state.get("past_campaign_insights", "")
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before recommend_channels")

    channel_prompt = load_prompt(
        "channel_recommendation_prompt",
        insights=insights,
        target_audience=strategy.target_audience if strategy else 'N/A',
        campaign_channels=strategy.campaign_channels if strategy else 'N/A',
        campaign_type=campaign_input.campaign_type,
        target_industry=campaign_input.target_industry,
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
    )

    try:
        recommendation = _invoke_structured_llm(ChannelRecommendation, channel_prompt)
        return {"channel_recommendation": recommendation}
    except Exception as e:
        logger.error(f"recommend_channels failed all retries: {e}. Executing fallback...")
        return _llm_fallback("recommend_channels", channel_prompt, "channel_recommendation", ChannelRecommendation,
                             {"primary_channels": "N/A", "channel_rationale": "N/A",
                              "expected_reach": "N/A"})


# ---------------------------------------------------------------------------
# Budget optimization node
# ---------------------------------------------------------------------------

def optimize_budget(state: GraphState) -> dict:
    """Create a detailed budget allocation plan across channels and timeline phases."""
    channel_rec = state.get("channel_recommendation")
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before optimize_budget")

    budget_prompt = load_prompt(
        "budget_optimization_prompt",
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
        goals=campaign_input.goals,
        primary_channels=channel_rec.primary_channels if channel_rec else 'N/A',
        channel_rationale=channel_rec.channel_rationale if channel_rec else 'N/A',
    )

    try:
        allocation = _invoke_structured_llm(BudgetAllocation, budget_prompt)
        return {"budget_allocation": allocation}
    except Exception as e:
        logger.error(f"optimize_budget failed all retries: {e}. Executing fallback...")
        return _llm_fallback("optimize_budget", budget_prompt, "budget_allocation", BudgetAllocation,
                             {"channel_breakdown": "N/A", "timeline_phases": "N/A",
                              "contingency_plan": "N/A"})


# ---------------------------------------------------------------------------
# Risk assessment node
# ---------------------------------------------------------------------------

def assess_risks(state: GraphState) -> dict:
    """Assess campaign risks and provide mitigation strategies."""
    strategy = state.get("strategy")
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before assess_risks")

    risk_prompt = load_prompt(
        "risk_assessment_prompt",
        campaign_type=campaign_input.campaign_type,
        target_industry=campaign_input.target_industry,
        target_audience=strategy.target_audience if strategy else 'N/A',
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
        channel_breakdown=strategy.campaign_channels if strategy else 'N/A',
        past_campaign_insights=state.get("past_campaign_insights", "N/A"),
    )

    try:
        assessment = _invoke_structured_llm(RiskAssessment, risk_prompt)
        return {"risk_assessment": assessment}
    except Exception as e:
        logger.warning(f"assess_risks failed all retries: {e}. Executing fallback...")
        return _llm_fallback("assess_risks", risk_prompt, "risk_assessment", RiskAssessment,
                             {"identified_risks": "N/A", "mitigation_strategies": "N/A",
                              "success_metrics": "N/A"})


# ---------------------------------------------------------------------------
# Fallback report generator
# ---------------------------------------------------------------------------

def generate_fallback_report(state: GraphState) -> str:
    """Generate a basic markdown report (fallback if LLM formatting fails)."""

    strategy = state.get('strategy')
    channels = state.get('channel_recommendation')
    budget = state.get('budget_allocation')
    risks = state.get('risk_assessment')
    insights = state.get('past_campaign_insights', '')
    trends = state.get('market_trends', '')
    campaign_input = state['campaign_input']
    if campaign_input is None:
        raise ValueError("campaign_input must be set before generate_fallback_report")

    return f"""# Marketing Campaign Strategy Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Campaign Overview

| Aspect | Details |
|--------|---------|
| Campaign Type | {campaign_input.campaign_type} |
| Target Industry | {campaign_input.target_industry} |
| Budget | {campaign_input.budget} |
| Timeline | {campaign_input.timeline} |
| Goals | {campaign_input.goals} |

---

## Data-Driven Insights
### Historical Campaign Analysis
{insights}

### Market Trends
{trends}

---

## Recommended Strategy
### Target Audience
{strategy.target_audience if strategy else 'N/A'}
### Campaign Channels
{strategy.campaign_channels if strategy else 'N/A'}
### Acquisition Cost Estimate
{strategy.acquisition_cost_estimate if strategy else 'N/A'}
### Expected ROI
{strategy.expected_roi if strategy else 'N/A'}

---

## Channel Recommendations
### Primary Channels
{channels.primary_channels if channels else 'N/A'}
### Channel Rationale
{channels.channel_rationale if channels else 'N/A'}
### Expected Reach & Engagement
{channels.expected_reach if channels else 'N/A'}

---

## Budget Optimization Plan
### Channel Breakdown
{budget.channel_breakdown if budget else 'N/A'}
### Timeline Phases
{budget.timeline_phases if budget else 'N/A'}
### Contingency Plan
{budget.contingency_plan if budget else 'N/A'}

---

## Risk Assessment & Mitigation
### Identified Risks
{risks.identified_risks if risks else 'N/A'}
### Mitigation Strategies
{risks.mitigation_strategies if risks else 'N/A'}
### Success Metrics & KPIs
{risks.success_metrics if risks else 'N/A'}    
"""


# ---------------------------------------------------------------------------
# Markdown-formatting node
# ---------------------------------------------------------------------------

import re as _re


def _sanitize_markdown(text: str) -> str:
    """Strip stray HTML tags that LLMs embed inside markdown (e.g. <br> in table cells)."""
    # Replace <br>, <br/>, <br /> (with optional surrounding whitespace) with a space
    text = _re.sub(r'\s*<br\s*/?>\s*', ' ', text, flags=_re.IGNORECASE)
    # Strip any remaining HTML tags except markdown-safe constructs
    text = _re.sub(r'</?(?:div|span|p|b|i|u|font|center|style|script|iframe)[^>]*>', '', text, flags=_re.IGNORECASE)
    return text


def format_markdown_report(state: GraphState) -> dict:
    """Format the strategy into a polished markdown document."""

    strategy = state.get('strategy')
    channels = state.get('channel_recommendation')
    budget = state.get('budget_allocation')
    risks = state.get('risk_assessment')
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before format_markdown_report")

    formatting_prompt = load_prompt(
        "markdown_formatting_prompt",
        campaign_type=campaign_input.campaign_type,
        target_industry=campaign_input.target_industry,
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
        goals=campaign_input.goals,
        past_campaign_insights=state.get("past_campaign_insights", "N/A"),
        market_trends=state.get("market_trends", "N/A"),
        target_audience=strategy.target_audience if strategy else 'N/A',
        campaign_channels=strategy.campaign_channels if strategy else 'N/A',
        acquisition_cost_estimate=strategy.acquisition_cost_estimate if strategy else 'N/A',
        expected_roi=strategy.expected_roi if strategy else 'N/A',
        primary_channels=channels.primary_channels if channels else 'N/A',
        channel_rationale=channels.channel_rationale if channels else 'N/A',
        expected_reach=channels.expected_reach if channels else 'N/A',
        channel_breakdown=budget.channel_breakdown if budget else 'N/A',
        timeline_phases=budget.timeline_phases if budget else 'N/A',
        contingency_plan=budget.contingency_plan if budget else 'N/A',
        identified_risks=risks.identified_risks if risks else 'N/A',
        mitigation_strategies=risks.mitigation_strategies if risks else 'N/A',
        success_metrics=risks.success_metrics if risks else 'N/A',
    )

    try:
        formatted_md = _invoke_llm(formatting_prompt)
        formatted_content = _extract_text(
            formatted_md.content if hasattr(formatted_md, 'content') else formatted_md
        )
        return {"formatted_markdown": _sanitize_markdown(formatted_content)}
    except Exception as e:
        logger.error(f"Markdown formatting failed: {e}")
        return {"formatted_markdown": _sanitize_markdown(generate_fallback_report(state))}


# ---------------------------------------------------------------------------
# Human approval + save nodes
# ---------------------------------------------------------------------------

def human_approval_step(state: GraphState) -> dict:
    """Ask user to review and approve the markdown before saving."""
    formatted_md = state.get('formatted_markdown', '')
    if formatted_md is None:
        raise ValueError("formatted_markdown must be set before human_approval_step")

    logger.info("=" * 70)
    logger.info("FORMATTED MARKDOWN REPORT")
    logger.info("=" * 70)
    logger.info(formatted_md[:2000])
    logger.info("\n... (partial report shown above) ...\n")

    if sys.stdin.isatty():
        approval = input("\n✓ Save the report to markdown? (yes/no): ").strip().lower()
        human_approved = approval in ['yes', 'y', 'true', '1']
    else:
        logger.info("Non-interactive mode detected — auto-approving report.")
        human_approved = True

    return {"human_approval": human_approved}


def save_approved_markdown(state: GraphState) -> dict:
    """Save the markdown file if approved by human."""

    if not state.get('human_approval', False):
        logger.info("Report NOT saved. No confirmation received.")
        return {"formatted_markdown": ""}

    formatted_md = state.get('formatted_markdown') or ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    filename = settings.outputs_dir / f"campaign_strategy_{timestamp}.md"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(formatted_md)
        logger.info(f"Report successfully saved to: {filename}")
        return {"formatted_markdown": str(filename)}
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return {"formatted_markdown": ""}
