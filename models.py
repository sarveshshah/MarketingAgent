"""Pydantic models and graph state definition."""

from typing import Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------

class CampaignInput(BaseModel):
    """Campaign input structure"""
    campaign_type: str = Field(description="The type of marketing campaign (e.g., product launch, brand awareness, retention).")
    target_industry: str = Field(description="The target industry or market segment for the campaign.")
    budget: str = Field(description="The budget allocated for the campaign.")
    timeline: str = Field(description="The timeline for the campaign (e.g., 3 months, Q1 2026).")
    goals: str = Field(description="Specific goals or KPIs (comma-separated) for the campaign.")


class CampaignStrategy(BaseModel):
    """Campaign strategy structure"""
    target_audience: str = Field(description="The target audience for the marketing campaign.")
    campaign_channels: str = Field(description="The channels to be used for the marketing campaign (e.g., email, social media, etc.).")
    acquisition_cost_estimate: str = Field(description="Estimated cost for customer acquisition through the campaign.")
    expected_roi: str = Field(description="Expected return on investment from the campaign.")


class ChannelRecommendation(BaseModel):
    """Channel recommendation structure"""
    primary_channels: str = Field(description="Top 2-3 recommended channels with percentages")
    channel_rationale: str = Field(description="Why these channels are recommended")
    expected_reach: str = Field(description="Estimated reach and engagement metrics")


class BudgetAllocation(BaseModel):
    """Budget allocation structure"""
    channel_breakdown: str = Field(description="Budget allocation by channel with percentages")
    timeline_phases: str = Field(description="Budget distribution across timeline phases")
    contingency_plan: str = Field(description="Suggested contingency (typically 10-15% reserve)")


class RiskAssessment(BaseModel):
    """Risk assessment structure"""
    identified_risks: str = Field(description="Key risks ranked by severity")
    mitigation_strategies: str = Field(description="Specific actions to mitigate each risk")
    success_metrics: str = Field(description="Key performance indicators to track")


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class GraphState(TypedDict):
    """Campaign state structure"""
    campaign_input: Optional[CampaignInput]
    past_campaign_insights: Optional[str]
    market_trends: Optional[str]
    strategy: Optional[CampaignStrategy]
    channel_recommendation: Optional[ChannelRecommendation]
    budget_allocation: Optional[BudgetAllocation]
    risk_assessment: Optional[RiskAssessment]
    formatted_markdown: Optional[str]
    human_approval: Optional[bool]
