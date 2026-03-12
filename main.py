# imports
"""Main"""
from datetime import datetime
import io
import json
import re
from functools import lru_cache
from typing import Annotated, Any, Optional
import logging
from pathlib import Path

import pandas as pd

from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_experimental.tools import PythonREPLTool
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from langchain_community.tools import DuckDuckGoSearchRun

from tenacity import retry, stop_after_attempt, wait_exponential

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from typing_extensions import TypedDict

# Load API keys from .env file immediately so they are available to third-party imports below
from dotenv import load_dotenv
load_dotenv()

# Reusable retry decorators
standard_retry = retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
fast_retry = retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))

# Set up logging to file and console
logs_dir = Path("logs")
logs_dir.mkdir(parents=True, exist_ok=True)

log_filename = logs_dir / f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create logger
logger = logging.getLogger("MarketingAgent")
logger.setLevel(logging.INFO)

# File handler with detailed format
file_handler = logging.FileHandler(log_filename, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)

# Console handler with simpler format
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(message)s")
console_handler.setFormatter(console_formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.info(f"MarketingAgent session started. Log file: {log_filename}")

# Suppress verbose logging from LangChain and related libraries
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


class Settings(BaseSettings):
    """Centralised configuration — values are read from .env or environment variables."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM model names
    openai_model: str = "gpt-5.1"
    gemini_model: str = "gemini-2.5-flash"          # used by search agent
    gemini_analyst_model: str = "gemini-2.5-pro" # used by data analysis agent

    # Retry / resilience
    max_retries: int = 2

    # File paths — anchored to main.py's directory so they work regardless of CWD
    data_path: Path = Path(__file__).parent / "data" / "marketing_campaign_dataset.csv"
    outputs_dir: Path = Path(__file__).parent / "outputs"
    llm_cache_path: str = ".langchain.db"


settings = Settings()

# Configure LLM response caching — must be set before any LLM client is instantiated
# Uses a local SQLite DB to avoid burning API tokens on identical prompts during dev/testing
set_llm_cache(SQLiteCache(database_path=settings.llm_cache_path))


@lru_cache(maxsize=1)
def _get_llm() -> ChatOpenAI:
    """Return the cached primary LLM (strategy, channels, budget, risks, report).
    Built lazily on first call so importing this module never creates real API clients.
    Call `_get_llm.cache_clear()` in tests to swap in a mock.
    """
    return ChatOpenAI(
        model=settings.openai_model, 
        temperature=0, 
        verbose=True
    )


@lru_cache(maxsize=1)
def _get_analyst_llm() -> ChatGoogleGenerativeAI:
    """Return the cached Gemini LLM used by the data-analysis agent."""
    return ChatGoogleGenerativeAI(
        model=settings.gemini_analyst_model, 
        temperature=0, 
        verbose=True
    )


@lru_cache(maxsize=1)
def _get_search_llm() -> Any:
    """Return the cached Gemini Search LLM (with Google Search tool bound).
    Returns None if initialization fails (e.g. missing API key).
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model, temperature=0, verbose=True
        )
        return llm.bind_tools([{"google_search": {}}])
    except Exception as e:
        logger.warning(f"Gemini Google Search could not be initialized: {e}. Will use DuckDuckGo exclusively.")
        return None

@lru_cache(maxsize=32)
def _read_template(prompt_name: str) -> str:
    """Read a template file from disk. Cached to avoid I/O on every call."""
    prompts_dir = Path(__file__).parent / "prompts"
    prompt_file = prompts_dir / f"{prompt_name}.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    with open(prompt_file, 'r', encoding='utf-8') as f:
        return f.read()

# Helper function to load and format prompt templates from the prompts directory
def load_prompt(prompt_name: str, **kwargs: Any) -> str:
    """
    Load a prompt template from the prompts directory and format it with variables.
    """
    template = _read_template(prompt_name)
    
    # Using **kwargs to make the function flexible and auto handle any variables needed for formatting the prompt
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required variable in prompt template: {e}") from e
    

# ---------------------------------------------------------------------------
# Shared LLM invocation helpers
# _get_structured_llm is cached (lru_cache) so with_structured_output() is
# only built once per Pydantic model class rather than on every node call.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def _get_structured_llm(model_cls: type):
    """Cached structured-output LLM per Pydantic model class."""
    return _get_llm().with_structured_output(model_cls)


@standard_retry
def _invoke_llm(prompt: str):
    """Retry-wrapped plain LLM invocation."""
    return _get_llm().invoke(prompt)


@standard_retry
def _invoke_structured_llm(model_cls: type, prompt: str):
    """Retry-wrapped structured-output LLM invocation."""
    return _get_structured_llm(model_cls).invoke(prompt)


# Input structure for the campaign details - this is what the user will provide at the start of the graph
# This was intentntiionally designed to be structured and not a free text input to ensure the LLM receives clear, consistent information to work with in the subsequent nodes.
class CampaignInput(BaseModel):
    """Campaign input structure"""
    campaign_type: str = Field(description="The type of marketing campaign (e.g., product launch, brand awareness, retention).")
    target_industry: str = Field(description="The target industry or market segment for the campaign.")
    budget: str = Field(description="The budget allocated for the campaign.")
    timeline: str = Field(description="The timeline for the campaign (e.g., 3 months, Q1 2026).")
    goals: str = Field(description="Specific goals or KPIs (comma-separated) for the campaign.")    

# Structure for the LLM to generate the strategy
class CampaignStrategy(BaseModel):
    """Campaign strategy structure"""
    target_audience: str = Field(description="The target audience for the marketing campaign.")
    campaign_channels: str = Field(description="The channels to be used for the marketing campaign (e.g., email, social media, etc.).")
    acquisition_cost_estimate: str = Field(description="Estimated cost for customer acquisition through the campaign.")
    expected_roi: str = Field(description="Expected return on investment from the campaign.")

# Structure for channel recommendations
class ChannelRecommendation(BaseModel):
    """Channel recommendation structure"""
    primary_channels: str = Field(description="Top 2-3 recommended channels with percentages")
    channel_rationale: str = Field(description="Why these channels are recommended")
    expected_reach: str = Field(description="Estimated reach and engagement metrics")

# Create a structured output format for budget allocation recommendations
class BudgetAllocation(BaseModel):
    """Budget allocation structure"""
    channel_breakdown: str = Field(description="Budget allocation by channel with percentages")
    timeline_phases: str = Field(description="Budget distribution across timeline phases")
    contingency_plan: str = Field(description="Suggested contingency (typically 10-15% reserve)")

# Identify potential risks and mitigation strategies
class RiskAssessment(BaseModel):
    """Risk assessment structure"""
    identified_risks: str = Field(description="Key risks ranked by severity")
    mitigation_strategies: str = Field(description="Specific actions to mitigate each risk")
    success_metrics: str = Field(description="Key performance indicators to track")

# Campaign state - includes both input and analysis results 
# This state will be passed through each node in the graph, allowing them to read and update the relevant fields as they perform their tasks.
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


# Initial node: Collect campaign input from user
def collect_campaign_input(state: GraphState) -> dict:
    """Collect marketing campaign information from user"""
    
    # If input is already provided in state (e.g. from UI), use it
    if state.get("campaign_input"):
        return {}

    # TEST INPUT 
    # campaign_input = {
    #     "campaign_type": "New Phone Launch",
    #     "target_industry": "High income earners",
    #     "budget": "100000",
    #     "timeline": "6 months",
    #     "goals": "Maximum engagement"
    # }
    
    print("\n=== Marketing Campaign Input ===\n")

    campaign_input = {
        "campaign_type": input("Campaign type (e.g., product launch, brand awareness, retention): ").strip(),
        "target_industry": input("Target industry or market segment: ").strip(),
        "budget": input("Budget allocated for campaign: ").strip(),
        "timeline": input("Timeline for campaign (e.g., 3 months, Q1 2026): ").strip(),
        "goals": input("Specific goals or KPIs (comma-separated): ").strip(),
    }
    
    return {"campaign_input": CampaignInput(**campaign_input)}


# Data analysis agent: uses Python REPL to analyze the dataframe
def data_analysis_agent(df: pd.DataFrame, analysis_prompt: str) -> str:
    """Data analysis agent that uses a Python REPL tool to analyze the dataframe and extract insights."""
    
    # Create a Python REPL tool with the dataframe in its local scope
    tools = [PythonREPLTool(locals={"df": df})]

    # Construct a prompt that includes the dataframe schema
    buffer = io.StringIO()
    df.info(buf=buffer)
    df_info = buffer.getvalue()
    df_preview = df.head().to_string()

    system_message = load_prompt(
        "_system_data_analysis_prompt",
        df_info = df_info,
        df_preview = df_preview
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    # lanchain's Pandas agent is brittle and seems to be abanadoned, so we are building a custom agent using the Python REPL tool which is more robust and allows us to have better control over the prompt and error handling. 
    # The agent will receive the analysis prompt, execute Python code to analyze the dataframe, and return the insights as text.
    agent = create_tool_calling_agent(_get_analyst_llm(), tools, prompt_template)
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True, 
        handle_parsing_errors=True,
    )
    
    @standard_retry
    def _invoke_agent(executor, prompt_input):
        return executor.invoke(prompt_input)

    # Execute the agent with the provided analysis prompt
    agent_response = _invoke_agent(agent_executor, {"input": analysis_prompt})
    data_insights = agent_response["output"]

    return data_insights

# First node: Analyze past campaigns
def analyze_past_campaigns(state: GraphState) -> dict:
    """Analyze past campaign data and return data-driven insights only.

    This node is responsible solely for extracting data insights from the
    dataset and returning them in the state under `past_campaign_insights`.
    The actual strategy generation is handled by a separate node.
    """
    logger.info("Analyzing past campaign data...")    
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before analyze_past_campaigns")

    try:
        # Hard coded for the POC perscpective, can be enhanced with a database connections or providing user the ability to upload their own dataset in the UI
        df = pd.read_csv(settings.data_path)

        # Load prompt template and format with variables
        data_analysis_prompt = load_prompt(
            "data_analysis_prompt",
            campaign_type=campaign_input.campaign_type,
            target_industry=campaign_input.target_industry
        )
        
        # Use the data analysis agent to extract insights
        data_insights = data_analysis_agent(df, data_analysis_prompt)
        
    except FileNotFoundError:
        logger.warning("marketing_campaign_dataset.csv not found.")
        data_insights = "Historical data unavailable - dataset file not found."
        
    except Exception as e:
        logger.exception("Could not analyze data with agent.")
        data_insights = f"Data analysis unavailable due to error: {str(e)[:200]}"

    # Return only the data insights to be consumed by the next node
    return {"past_campaign_insights": data_insights}


# Search agent: conducts Google searches primarily via Gemini, falling back to DuckDuckGo 
def search_agent(queries: list) -> str:
    """Execute search queries using Gemini Google Search (primary) or DuckDuckGo (fallback)."""
    
    gemini_search_llm = _get_search_llm()
    has_gemini_search = gemini_search_llm is not None
    ddg_tool = DuckDuckGoSearchRun()

    @fast_retry
    def _search_google(query: str) -> str:
        response = gemini_search_llm.invoke(f"Perform a comprehensive Google search and summarize the findings for: {query}")
        content = response.content
        # Gemini grounded responses can return a list of content blocks
        if isinstance(content, list):
            return " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            ).strip()
        return str(content)

    @standard_retry
    def _search_ddg(query: str) -> str:
        return ddg_tool.invoke(query)

    all_results = []
    
    logger.info("Executing search queries...")
    for query in queries:
        logger.info(f"  Running query: {query}")
        
        # Try Gemini Google Search first if available
        if has_gemini_search:
            try:
                results = _search_google(query)
                all_results.append(f"--- GEMINI GOOGLE SEARCH RESULTS FOR QUERY: {query} ---\n{results}")
                continue # Success, move to next query
            except Exception as e:
                logger.warning(f"Gemini Google search failed for '{query}': {e}. Falling back to DuckDuckGo.")
        
        # Fallback to DuckDuckGo
        try:
            results = _search_ddg(query)
            all_results.append(f"--- DUCKDUCKGO RESULTS FOR QUERY: {query} ---\n{results}")
        except Exception as e:
            logger.error(f"Both search methods failed for '{query}'. Error: {e}")
            all_results.append(f"--- ALL SEARCHES FAILED FOR QUERY: {query} ---")
            
    search_results_text = "\n\n".join(all_results)
    return search_results_text


# Second node: Conduct market research using search queries and synthesize results into market trends
def conduct_market_research(state: GraphState) -> dict:
    """
    Conducts robust market research by running multiple search queries
    and synthesizing the results into a coherent summary of market trends.
    """

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
        current_year=datetime.now().year
    )
    
    try:
        logger.info("Generating dynamic search queries...")
        queries_response = _invoke_llm(search_queries_prompt)
        content = queries_response.content if hasattr(queries_response, 'content') else queries_response
        
        # Try to parse the content as JSON using pydantic or json        
        # Find json array in the string
        json_match = re.search(r'\[(.*?)\]', str(content), re.DOTALL)
        if json_match:
            queries = json.loads(f"[{json_match.group(1)}]")
            # Ensure it's a list of strings
            if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
                raise ValueError("Parsed JSON is not a list of strings")
        else:
            raise ValueError("No JSON array found in LLM response")
            
    except Exception as e:
        logger.warning(f"Failed to dynamically generate search queries: {e}. Falling back to default queries.")
        queries = [
            f"latest marketing trends for {campaign_input.campaign_type} in {campaign_input.target_industry} industry {datetime.now().year}",
            f"consumer behavior trends and preferences in {campaign_input.target_industry} {datetime.now().year}",
            f"successful marketing strategies for {campaign_input.campaign_type} targeting {campaign_input.target_industry}",
            f"emerging marketing channels and technologies for {campaign_input.target_industry}"
        ]
    
    # 2. Execute searches using the search agent
    search_results_text = search_agent(queries)
    
    # 3. Compile the results with an LLM
    logger.info("Synthesizing market trends from search results...")
    
    # Load prompt template and format with variables
    market_research_prompt = load_prompt(
        "market_research_prompt",
        campaign_type = campaign_input.campaign_type,
        target_industry = campaign_input.target_industry,
        search_results = search_results_text,
    )
    

    try:
        response = _invoke_llm(market_research_prompt)
        content = response.content if hasattr(response, 'content') else response

        if isinstance(content, list) and content and isinstance(content[0], dict) and 'text' in content[0]:
            compiled_trends = content[0]['text']
        else:
            compiled_trends = str(content)
            
        logger.info("Successfully synthesized market trends.")
    except Exception as e:
        logger.error(f"Market research synthesis failed: {e}")
        # As a fallback, return the raw (but truncated) search results
        compiled_trends = "Market trend synthesis failed. Raw data follows:\n\n" + search_results_text[:2000]

    return {"market_trends": compiled_trends}

def _llm_fallback(node_name: str, prompt: str, state_key: str, model_cls: type, fallback_fields: dict) -> dict:
    """Run the plain LLM (no structured output) as a last-resort fallback.

    Args:
        node_name:      Human-readable name used in log messages.
        prompt:         The already-formatted prompt string to send to the LLM.
        state_key:      The GraphState field to write the result into (e.g. "strategy").
        model_cls:      The Pydantic model class to instantiate (e.g. CampaignStrategy).
        fallback_fields: N/A defaults for every field — first field is overwritten with
                         the raw LLM text if the unstructured call succeeds.
    """
    first_field = list(model_cls.model_fields)[0]     # first field of the pydantic model
    logger.warning("Structured output failed for %s. Using text fallback.", node_name)
    try:
        response = _get_llm().invoke(prompt)
        content = str(response.content if hasattr(response, "content") else response)
        fields = {**fallback_fields, first_field: content[:500] + " ... (text fallback)"}
        return {state_key: model_cls(**fields)}
    except Exception as e:
        logger.error("Fallback text LLM also failed for %s: %s", node_name, e)
        return {state_key: model_cls(**fallback_fields)}


# Third node: Generate the high-level marketing strategy based on the data insights and market trends
def generate_strategy(state: GraphState) -> dict:
    """Generate a structured marketing strategy using the data insights."""
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before generate_strategy")
    data_insights = state.get("past_campaign_insights", "")
    market_trends = state.get("market_trends", "")

    # Load prompt template and format with variables
    strategy_prompt = load_prompt(
        "strategy_generation_prompt",
        data_insights=data_insights,
        market_trends=market_trends,
        campaign_type=campaign_input.campaign_type,
        target_industry=campaign_input.target_industry,
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
        goals=campaign_input.goals
    )

    try:
        strategy = _invoke_structured_llm(CampaignStrategy, strategy_prompt)
        return {"strategy": strategy}
    except Exception as e:
        logger.error(f"generate_strategy failed all retries: {e}. Executing fallback...")
        return _llm_fallback("generate_strategy", strategy_prompt, "strategy", CampaignStrategy,
                             {"target_audience": "N/A", "campaign_channels": "N/A",
                              "acquisition_cost_estimate": "N/A", "expected_roi": "N/A"})

# Fourth node: Recommend specific marketing channels based on the strategy and data insights
def recommend_channels(state: GraphState) -> dict:
    """Recommend specific marketing channels based on data insights and campaign profile."""
    strategy = state.get("strategy")
    insights = state.get("past_campaign_insights", "")
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before recommend_channels")

    # Load prompt template and format with variables
    channel_prompt = load_prompt(
        "channel_recommendation_prompt",
        insights=insights,
        target_audience=strategy.target_audience if strategy else 'N/A',
        campaign_channels=strategy.campaign_channels if strategy else 'N/A',
        campaign_type=campaign_input.campaign_type,
        target_industry=campaign_input.target_industry,
        budget=campaign_input.budget,
        timeline=campaign_input.timeline
    )
    
    try:
        recommendation = _invoke_structured_llm(ChannelRecommendation, channel_prompt)
        return {"channel_recommendation": recommendation}
    except Exception as e:
        logger.error(f"recommend_channels failed all retries: {e}. Executing fallback...")
        return _llm_fallback("recommend_channels", channel_prompt, "channel_recommendation", ChannelRecommendation,
                             {"primary_channels": "N/A", "channel_rationale": "N/A",
                              "expected_reach": "N/A"})

# Fifth node: Optimize the budget allocation across channels and timeline phases
def optimize_budget(state: GraphState) -> dict:
    """Create a detailed budget allocation plan across channels and timeline phases."""
    channel_rec = state.get("channel_recommendation")
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before optimize_budget")

    # Load prompt template and format with variables
    budget_prompt = load_prompt(
        "budget_optimization_prompt",
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
        goals=campaign_input.goals,
        primary_channels=channel_rec.primary_channels if channel_rec else 'N/A',
        channel_rationale=channel_rec.channel_rationale if channel_rec else 'N/A'
    )
    
    try:
        allocation = _invoke_structured_llm(BudgetAllocation, budget_prompt)
        return {"budget_allocation": allocation}
    except Exception as e:
        logger.error(f"optimize_budget failed all retries: {e}. Executing fallback...")
        return _llm_fallback("optimize_budget", budget_prompt, "budget_allocation", BudgetAllocation,
                             {"channel_breakdown": "N/A", "timeline_phases": "N/A",
                              "contingency_plan": "N/A"})

# Sixth node: Assess campaign risks and provide mitigation strategies
def assess_risks(state: GraphState) -> dict:
    """Assess campaign risks and provide mitigation strategies."""
    strategy = state.get("strategy")
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before assess_risks")

    # Load prompt template and format with variables
    risk_prompt = load_prompt(
        "risk_assessment_prompt",
        campaign_type=campaign_input.campaign_type,
        target_industry=campaign_input.target_industry,
        target_audience=strategy.target_audience if strategy else 'N/A',
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
        channel_breakdown=strategy.campaign_channels if strategy else 'N/A',
        past_campaign_insights=state.get("past_campaign_insights", "N/A")
    )
    
    try:
        assessment = _invoke_structured_llm(RiskAssessment, risk_prompt)
        return {"risk_assessment": assessment}
    except Exception as e:
        logger.warning(f"assess_risks failed all retries: {e}. Executing fallback...")
        return _llm_fallback("assess_risks", risk_prompt, "risk_assessment", RiskAssessment,
                             {"identified_risks": "N/A", "mitigation_strategies": "N/A",
                              "success_metrics": "N/A"})


# Helper node to generate a fallback markdown report if the LLM formatting fails at the end
def generate_fallback_report(state: GraphState) -> str:
    """Generate a basic markdown report (fallback if LLM formatting fails)"""
    
    strategy = state.get('strategy')
    channels = state.get('channel_recommendation')
    budget = state.get('budget_allocation')
    risks = state.get('risk_assessment')
    insights = state.get('past_campaign_insights', '')
    trends = state.get('market_trends', '')
    campaign_input = state['campaign_input']
    if campaign_input is None:
        raise ValueError("campaign_input must be set before generate_fallback_report")

    # Hardcoded markdown as a fallback if agent fails
    markdown_content = f"""# Marketing Campaign Strategy Report

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
    return markdown_content

# Helper node: Format the entire strategy into a polished markdown report
def format_markdown_report(state: GraphState) -> dict:
    """Format the strategy into a beautiful, well-structured markdown document.
    
    Uses an LLM to enhance the markdown with better formatting, sections,
    and professional presentation.
    """
    
    strategy = state.get('strategy')
    channels = state.get('channel_recommendation')
    budget = state.get('budget_allocation')
    risks = state.get('risk_assessment')
    campaign_input = state["campaign_input"]
    if campaign_input is None:
        raise ValueError("campaign_input must be set before format_markdown_report")

    # Load prompt template and format with variables
    formatting_prompt = load_prompt(
        "markdown_formatting_prompt",
        campaign_type = campaign_input.campaign_type,
        target_industry = campaign_input.target_industry,
        budget = campaign_input.budget,
        timeline = campaign_input.timeline,
        goals = campaign_input.goals,
        past_campaign_insights = state.get("past_campaign_insights", "N/A"),
        market_trends = state.get("market_trends", "N/A"),
        target_audience = strategy.target_audience if strategy else 'N/A',
        campaign_channels = strategy.campaign_channels if strategy else 'N/A',
        acquisition_cost_estimate = strategy.acquisition_cost_estimate if strategy else 'N/A',
        expected_roi = strategy.expected_roi if strategy else 'N/A',
        primary_channels = channels.primary_channels if channels else 'N/A',
        channel_rationale = channels.channel_rationale if channels else 'N/A',
        expected_reach = channels.expected_reach if channels else 'N/A',
        channel_breakdown = budget.channel_breakdown if budget else 'N/A',
        timeline_phases = budget.timeline_phases if budget else 'N/A',
        contingency_plan = budget.contingency_plan if budget else 'N/A',
        identified_risks = risks.identified_risks if risks else 'N/A',
        mitigation_strategies = risks.mitigation_strategies if risks else 'N/A',
        success_metrics = risks.success_metrics if risks else 'N/A'
    )
    
    try:
        formatted_md = _invoke_llm(formatting_prompt)
        content = formatted_md.content if hasattr(formatted_md, 'content') else formatted_md
        
        if isinstance(content, list) and content and isinstance(content[0], dict) and 'text' in content[0]:
            formatted_content = content[0]['text']
        else:
            formatted_content = str(content)

        return {"formatted_markdown": formatted_content}
    except Exception as e:
        logger.error(f"Markdown formatting failed: {e}")
        # Fallback to basic structure
        return {"formatted_markdown": generate_fallback_report(state)}

# Final node: Ask for human approval before saving the markdown report to a file
def human_approval_step(state: GraphState) -> dict:
    """Ask user to review and approve the markdown before saving.
    
    Displays the formatted markdown and waits for user confirmation.
    """
    formatted_md = state.get('formatted_markdown', '')
    if formatted_md is None:
        raise ValueError("formatted_markdown must be set before human_approval_step")

    # For UI so that humans can see the whole report and ask further questions or chose to redo analysis
    logger.info("=" * 70)
    logger.info("FORMATTED MARKDOWN REPORT")
    logger.info("=" * 70)
    logger.info(formatted_md[:2000])  # Preview first 2000 chars
    logger.info("\n... (partial report shown above) ...\n")
    approval = input("\n✓ Save the report to markdown? (yes/no): ").strip().lower()
    human_approved = approval in ['yes', 'y', 'true', '1']
    
    return {"human_approval": human_approved}

# Helper node: Save the markdown report to a file if approved by human, otherwise skip saving
def save_approved_markdown(state: GraphState) -> dict:
    """Save the markdown file if approved by human.
    
    Only executes if human_approval is True.
    Returns the filename or None if not approved.
    """
    
    if not state.get('human_approval', False):
        logger.info("Report NOT saved. No confirmation received.")
        return {"formatted_markdown": ""}  # Clear from state
    
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


def build_graph(include_human_approval: bool = True) -> StateGraph:
    """Build the LangGraph pipeline, optionally skipping human approval steps."""
    builder = StateGraph(GraphState)
    builder.add_node("collect_campaign_input", collect_campaign_input)
    builder.add_node("analyze_past_campaigns", analyze_past_campaigns)
    builder.add_node("conduct_market_research", conduct_market_research)
    builder.add_node("generate_strategy", generate_strategy)
    builder.add_node("recommend_channels", recommend_channels)
    builder.add_node("optimize_budget", optimize_budget)
    builder.add_node("assess_risks", assess_risks)
    builder.add_node("format_markdown_report", format_markdown_report)

    if include_human_approval:
        builder.add_node("human_approval_step", human_approval_step)
        builder.add_node("save_approved_markdown", save_approved_markdown)

    builder.add_edge(START, "collect_campaign_input")

    # Parallel execution: both nodes only depend on campaign_input
    builder.add_edge("collect_campaign_input", "analyze_past_campaigns")
    builder.add_edge("collect_campaign_input", "conduct_market_research")

    # generate_strategy waits for both parallel nodes to complete
    builder.add_edge("analyze_past_campaigns", "generate_strategy")
    builder.add_edge("conduct_market_research", "generate_strategy")

    builder.add_node("wait_for_budget", lambda state: {})

    # Parallel fan-out
    builder.add_edge("generate_strategy", "recommend_channels")
    builder.add_edge("generate_strategy", "assess_risks")

    builder.add_edge("recommend_channels", "optimize_budget")
    
    # Pad the shorter parallel branch with a dummy node so it aligns topologically.
    # LangGraph only cleanly merges parallel execution paths if they share the same 'superstep' depth.
    builder.add_edge("assess_risks", "wait_for_budget")

    # Static Fan-In: Both paths are exactly 2 nodes deep. 
    # LangGraph will now perfectly merge them to format_markdown_report without double-execution!
    builder.add_edge("optimize_budget", "format_markdown_report")
    builder.add_edge("wait_for_budget", "format_markdown_report")

    if include_human_approval:
        builder.add_edge("format_markdown_report", "human_approval_step")
        builder.add_edge("human_approval_step", "save_approved_markdown")
        builder.add_edge("save_approved_markdown", END)
    else:
        builder.add_edge("format_markdown_report", END)

    return builder


def run_campaign(campaign_input: CampaignInput, include_human_approval: bool = False) -> dict:
    """Run the graph with a pre-supplied campaign input and return the final state."""
    app = build_graph(include_human_approval=include_human_approval).compile()
    initial_state = {"campaign_input": campaign_input}
    return app.invoke(initial_state)


def main() -> None:
    """Main function to run the LangGraph."""
    logger.info("Starting LangGraph execution...")
    app = build_graph(include_human_approval=True).compile()

    # Prepare initial state with both input and placeholder values for output fields
    initial_state = {
        "campaign_input": None
    }

    # Run graph with user-provided campaign input
    logger.info("Analyzing campaign requirements...")
    app.invoke(initial_state)
    logger.info("Campaign analysis complete.")


if __name__ == "__main__":
    main()