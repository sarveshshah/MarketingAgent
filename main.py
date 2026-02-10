from dotenv import load_dotenv
from typing import Any, Annotated, Literal, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
import pandas as pd
from datetime import datetime

load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

# Structure for the LLM to generate the strategy
class CampaignStrategy(BaseModel):
    target_audience: str = Field(description="The target audience for the marketing campaign.")
    campaign_channels: str = Field(description="The channels to be used for the marketing campaign (e.g., email, social media, etc.).")
    acquisition_cost_estimate: str = Field(description="Estimated cost for customer acquisition through the campaign.")
    expected_roi: str = Field(description="Expected return on investment from the campaign.")

class ChannelRecommendation(BaseModel):
    primary_channels: str = Field(description="Top 2-3 recommended channels with percentages")
    channel_rationale: str = Field(description="Why these channels are recommended")
    expected_reach: str = Field(description="Estimated reach and engagement metrics")

class BudgetAllocation(BaseModel):
    channel_breakdown: str = Field(description="Budget allocation by channel with percentages")
    timeline_phases: str = Field(description="Budget distribution across timeline phases")
    contingency_plan: str = Field(description="Suggested contingency (typically 10-15% reserve)")

class RiskAssessment(BaseModel):
    identified_risks: str = Field(description="Key risks ranked by severity")
    mitigation_strategies: str = Field(description="Specific actions to mitigate each risk")
    success_metrics: str = Field(description="Key performance indicators to track")

# Campaign state - includes both input and analysis results
class GraphState(TypedDict):
    campaign_type: str
    target_industry: str
    budget: str
    timeline: str
    goals: str
    past_campaign_insights: str
    strategy: Optional[CampaignStrategy]
    channel_recommendation: Optional[ChannelRecommendation]
    budget_allocation: Optional[BudgetAllocation]
    risk_assessment: Optional[RiskAssessment]

def analyze_past_campaigns(state: GraphState) -> dict:
    """Analyze past campaign data and return data-driven insights only.

    This node is responsible solely for extracting data insights from the
    dataset and returning them in the state under `past_campaign_insights`.
    The actual strategy generation is handled by a separate node.
    """

    df = pd.read_csv("data/marketing_campaign_dataset.csv")

    agent = create_pandas_dataframe_agent(
        llm,
        df,
        verbose=False,
        allow_dangerous_code=True,
    )

    data_analysis_prompt = f"""
    You are a data analyst specializing in marketing campaigns. 
    Analyze the marketing campaign dataset to answer these specific questions for a {state.get('campaign_type', 'general')} campaign targeting {state.get('target_industry', 'the market')}:

    1. Top performing channels by conversion rate and ROI
    2. Average customer acquisition costs (CAC) across channels
    3. Audience demographics with highest conversion rates
    4. Typical campaign durations
    5. Best performing campaign types and typical ROI
    6. Budget allocation recommendations based on historical data

    Return clear data points, lists, and numeric metrics where possible.
    """

    try:
        agent_response = agent.invoke(data_analysis_prompt)
        data_insights = str(agent_response)
    except Exception as e:
        print(f"Warning: Could not analyze data with agent. Error: {e}")
        data_insights = "Data analysis unavailable"

    # Return only the data insights to be consumed by the next node
    return {"past_campaign_insights": data_insights}


def generate_strategy(state: GraphState) -> dict:
    """Generate a structured marketing strategy using the data insights.

    Expects `past_campaign_insights` to be present in the state.
    Returns structured fields that update the state.
    """
    
    structured_llm = llm.with_structured_output(CampaignStrategy)

    data_insights = state.get("past_campaign_insights", "")

    strategy_prompt = f"""
    Using the following historical campaign analysis:

    {data_insights}

    Create a concise, data-driven marketing strategy for the user's requested campaign:
    - Campaign Type: {state.get('campaign_type', 'N/A')}
    - Target Industry: {state.get('target_industry', 'N/A')}
    - Budget: {state.get('budget', 'N/A')}
    - Timeline: {state.get('timeline', 'N/A')}
    - Goals: {state.get('goals', 'N/A')}

    Provide:
    1. `target_audience` as a short description
    2. `campaign_channels` as a comma-separated list
    3. `acquisition_cost_estimate` as a short numeric estimate or range
    4. `expected_roi` as a short estimate

    Make sure each recommendation explicitly references the data points from the analysis where applicable.
    """

    try:
        strategy = structured_llm.invoke(strategy_prompt)
    except Exception as e:
        print(f"Warning: structured LLM failed: {e}. Falling back to text LLM.")
        # fallback to the plain LLM interface if necessary
        strategy_text = llm.invoke(strategy_prompt)
        # best-effort parse: put the whole text into target_audience for visibility
        return {"strategy": CampaignStrategy(
            target_audience=str(strategy_text.content),
            campaign_channels="N/A",
            acquisition_cost_estimate="N/A",
            expected_roi="N/A"
        )}

    return {"strategy": strategy}


def recommend_channels(state: GraphState) -> dict:
    """Recommend specific marketing channels based on data insights and campaign profile.
    
    Uses the data insights and strategy to provide detailed channel recommendations
    with reasoning and expected performance metrics.
    """
    
    structured_llm = llm.with_structured_output(ChannelRecommendation)
    
    strategy = state.get("strategy")
    insights = state.get("past_campaign_insights", "")
    
    channel_prompt = f"""
    Based on this data analysis:
    {insights}
    
    And this marketing strategy:
    - Target Audience: {strategy.target_audience if strategy else 'N/A'}
    - Campaign Type: {state.get('campaign_type', 'N/A')}
    - Industry: {state.get('target_industry', 'N/A')}
    - Budget: {state.get('budget', 'N/A')}
    - Timeline: {state.get('timeline', 'N/A')}
    
    Recommend the 2-3 best marketing channels with:
    1. Specific channel names and recommended budget percentages
    2. Clear rationale based on the data insights and campaign profile
    3. Expected reach, engagement rates, and conversion metrics for each channel
    
    Prioritize channels with the highest ROI for this specific campaign type and audience.
    """
    
    try:
        recommendation = structured_llm.invoke(channel_prompt)
        return {"channel_recommendation": recommendation}
    except Exception as e:
        print(f"Warning: Channel recommendation failed: {e}")
        return {"channel_recommendation": ChannelRecommendation(
            primary_channels="Unable to generate recommendations",
            channel_rationale=str(e),
            expected_reach="N/A"
        )}


def optimize_budget(state: GraphState) -> dict:
    """Create a detailed budget allocation plan across channels and timeline phases.
    
    Breaks down the campaign budget into specific allocations by channel and
    across different timeline phases, with contingency planning.
    """
    
    structured_llm = llm.with_structured_output(BudgetAllocation)
    
    channel_rec = state.get("channel_recommendation")
    budget = state.get("budget", "$0")
    timeline = state.get("timeline", "N/A")
    goals = state.get("goals", "N/A")
    
    budget_prompt = f"""
    Create a detailed budget allocation plan for this campaign:
    - Total Budget: {budget}
    - Timeline: {timeline}
    - Goals: {goals}
    - Recommended Channels: {channel_rec.primary_channels if channel_rec else 'N/A'}
    
    Provide:
    1. Specific budget allocation by channel with percentages (e.g., "Email: 35%, Social Media: 40%, Display: 25%")
    2. Time-based phases (e.g., "Phase 1 Launch: 40%, Phase 2 Growth: 35%, Phase 3 Optimization: 25%")
    3. Contingency planning recommendation (typically 10-15% reserve)
    
    Ensure the percentages add up to 100% and align with the channel recommendations.
    """
    
    try:
        allocation = structured_llm.invoke(budget_prompt)
        return {"budget_allocation": allocation}
    except Exception as e:
        print(f"Warning: Budget optimization failed: {e}")
        return {"budget_allocation": BudgetAllocation(
            channel_breakdown="Unable to generate breakdown",
            timeline_phases="N/A",
            contingency_plan="N/A"
        )}


def assess_risks(state: GraphState) -> dict:
    """Assess campaign risks and provide mitigation strategies.
    
    Identifies potential risks specific to the campaign and provides
    actionable mitigation strategies and success metrics.
    """
    
    structured_llm = llm.with_structured_output(RiskAssessment)
    
    strategy = state.get("strategy")
    budget_alloc = state.get("budget_allocation")
    
    risk_prompt = f"""
    Assess risks for this marketing campaign:
    - Campaign Type: {state.get('campaign_type', 'N/A')}
    - Target Industry: {state.get('target_industry', 'N/A')}
    - Budget: {state.get('budget', 'N/A')}
    - Timeline: {state.get('timeline', 'N/A')}
    - Target Audience: {strategy.target_audience if strategy else 'N/A'}
    - Channels: {budget_alloc.channel_breakdown if budget_alloc else 'N/A'}
    
    Provide:
    1. Top 3-5 risks ranked by severity (High/Medium/Low) with brief descriptions
    2. Specific mitigation strategies for each identified risk
    3. Key success metrics to track and early warning indicators
    
    Focus on realistic, actionable risks for this specific campaign profile.
    """
    
    try:
        assessment = structured_llm.invoke(risk_prompt)
        return {"risk_assessment": assessment}
    except Exception as e:
        print(f"Warning: Risk assessment failed: {e}")
        return {"risk_assessment": RiskAssessment(
            identified_risks="Unable to assess risks",
            mitigation_strategies="N/A",
            success_metrics="N/A"
        )}


def collect_campaign_input() -> dict:
    """Collect marketing campaign information from user"""
    print("\n=== Marketing Campaign Input ===\n")
    
    campaign_input = {
        "campaign_type": input("Campaign type (e.g., product launch, brand awareness, retention): ").strip(),
        "target_industry": input("Target industry or market segment: ").strip(),
        "budget": input("Budget allocated for campaign: ").strip(),
        "timeline": input("Timeline for campaign (e.g., 3 months, Q1 2026): ").strip(),
        "goals": input("Specific goals or KPIs (comma-separated): ").strip(),
    }
    
    return campaign_input

# Build the graph
builder = StateGraph(GraphState)
builder.add_node("analyze_past_campaigns", analyze_past_campaigns)
builder.add_node("generate_strategy", generate_strategy)
builder.add_node("recommend_channels", recommend_channels)
builder.add_node("optimize_budget", optimize_budget)
builder.add_node("assess_risks", assess_risks)

builder.add_edge(START, "analyze_past_campaigns")
builder.add_edge("analyze_past_campaigns", "generate_strategy")
builder.add_edge("generate_strategy", "recommend_channels")
builder.add_edge("recommend_channels", "optimize_budget")
builder.add_edge("optimize_budget", "assess_risks")
builder.add_edge("assess_risks", END)

app = builder.compile()

# Collect user input for campaign
# campaign_input = collect_campaign_input()
campaign_input = {
    'campaign_type': "Phone Launch",
    'target_industry': "Consumer Electronics",
    'budget': "$50,000",
    'timeline': "3 months",
    'goals': "Increase brand awareness, Drive sales conversions"
}

# Prepare initial state with both input and placeholder values for output fields
initial_state = {
    "campaign_type": campaign_input["campaign_type"],
    "target_industry": campaign_input["target_industry"],
    "budget": campaign_input["budget"],
    "timeline": campaign_input["timeline"],
    "goals": campaign_input["goals"],
    "past_campaign_insights": "",
    "strategy": None,
    "channel_recommendation": None,
    "budget_allocation": None,
    "risk_assessment": None
}

# Run graph with user-provided campaign input
print("\nAnalyzing campaign requirements...")
result = app.invoke(initial_state)
print("\n" + "="*70)
print("MARKETING CAMPAIGN STRATEGY REPORT")
print("="*70)

print("\n📊 DATA-DRIVEN INSIGHTS (Historical Campaign Analysis):")
print("-" * 70)
print(result.get('past_campaign_insights', 'No insights available')[:500])

print("\n" + "="*70)
print("🎯 RECOMMENDED STRATEGY")
print("="*70)

strategy = result.get('strategy')
if strategy:
    print(f"\n👥 Target Audience:\n{strategy.target_audience}")
    print(f"\n📢 Campaign Channels:\n{strategy.campaign_channels}")
    print(f"\n💰 Acquisition Cost Estimate:\n{strategy.acquisition_cost_estimate}")
    print(f"\n📈 Expected ROI:\n{strategy.expected_roi}")

print("\n" + "="*70)
print("📡 CHANNEL RECOMMENDATIONS")
print("="*70)

channels = result.get('channel_recommendation')
if channels:
    print(f"\n🔝 Primary Channels:\n{channels.primary_channels}")
    print(f"\n💭 Rationale:\n{channels.channel_rationale}")
    print(f"\n🎯 Expected Reach:\n{channels.expected_reach}")

print("\n" + "="*70)
print("💵 BUDGET OPTIMIZATION")
print("="*70)

budget = result.get('budget_allocation')
if budget:
    print(f"\n📊 Channel Breakdown:\n{budget.channel_breakdown}")
    print(f"\n📅 Timeline Phases:\n{budget.timeline_phases}")
    print(f"\n🛡️ Contingency Plan:\n{budget.contingency_plan}")

print("\n" + "="*70)
print("⚠️  RISK ASSESSMENT & MITIGATION")
print("="*70)

risks = result.get('risk_assessment')
if risks:
    print(f"\n🚨 Identified Risks:\n{risks.identified_risks}")
    print(f"\n✅ Mitigation Strategies:\n{risks.mitigation_strategies}")
    print(f"\n📊 Success Metrics:\n{risks.success_metrics}")

print("\n" + "="*70)