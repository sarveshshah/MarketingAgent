# imports
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import logging

from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_experimental.tools import PythonREPLTool
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun

from tenacity import retry, stop_after_attempt, wait_exponential
import io

from typing import Any, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

# Load API keys from .env file
load_dotenv()

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

logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info(f"MarketingAgent session started. Log file: {log_filename}")

# Suppress verbose logging from LangChain and related libraries
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# LLM configurations - you can use same model for both nodes or different ones depending on the task requirements
# I found that Gemini was able to produce stronger data insights while ChatGPT was better at writing the report
data_analyst_llm = ChatGoogleGenerativeAI(
    model="gemini-3-pro-preview", 
    temperature=0, 
    verbose=True
)

llm = ChatOpenAI(
    model="gpt-5.1", 
    temperature=0, 
    verbose=True
)

# Helper function to load and format prompt templates from the prompts directory
def load_prompt(prompt_name: str, **kwargs: Any) -> str:
    """
    Load a prompt template from the prompts directory and format it with variables.
    """
    # Assuming prompts are in a 'prompts' folder relative to main.py
    prompts_dir = Path(__file__).parent / "prompts"
    prompt_file = prompts_dir / f"{prompt_name}.txt"
    
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    
    with open(prompt_file, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Using **kwargs to make the function flexible and auto handle any variables needed for formatting the prompt
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required variable in prompt template: {e}")
    

# Input structure for the campaign details - this is what the user will provide at the start of the graph
# This was intentntiionally designed to be structured and not a free text input to ensure the LLM receives clear, consistent information to work with in the subsequent nodes.
class CampaignInput(BaseModel):
    campaign_type: str = Field(description="The type of marketing campaign (e.g., product launch, brand awareness, retention).")
    target_industry: str = Field(description="The target industry or market segment for the campaign.")
    budget: str = Field(description="The budget allocated for the campaign.")
    timeline: str = Field(description="The timeline for the campaign (e.g., 3 months, Q1 2026).")
    goals: str = Field(description="Specific goals or KPIs (comma-separated) for the campaign.")    

# Structure for the LLM to generate the strategy
class CampaignStrategy(BaseModel):
    target_audience: str = Field(description="The target audience for the marketing campaign.")
    campaign_channels: str = Field(description="The channels to be used for the marketing campaign (e.g., email, social media, etc.).")
    acquisition_cost_estimate: str = Field(description="Estimated cost for customer acquisition through the campaign.")
    expected_roi: str = Field(description="Expected return on investment from the campaign.")

# Structure for channel recommendations
class ChannelRecommendation(BaseModel):
    primary_channels: str = Field(description="Top 2-3 recommended channels with percentages")
    channel_rationale: str = Field(description="Why these channels are recommended")
    expected_reach: str = Field(description="Estimated reach and engagement metrics")

# Create a structured output format for budget allocation recommendations
class BudgetAllocation(BaseModel):
    channel_breakdown: str = Field(description="Budget allocation by channel with percentages")
    timeline_phases: str = Field(description="Budget distribution across timeline phases")
    contingency_plan: str = Field(description="Suggested contingency (typically 10-15% reserve)")

# Identify potential risks and mitigation strategies
class RiskAssessment(BaseModel):
    identified_risks: str = Field(description="Key risks ranked by severity")
    mitigation_strategies: str = Field(description="Specific actions to mitigate each risk")
    success_metrics: str = Field(description="Key performance indicators to track")

# Campaign state - includes both input and analysis results 
# This state will be passed through each node in the graph, allowing them to read and update the relevant fields as they perform their tasks.
class GraphState(TypedDict):
    campaign_input: Optional[CampaignInput]
    past_campaign_insights: str
    market_trends: str
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
    
    # Tenacity retry logic helps with the brittleness of the agent execution. 
    # It will retry up to 3 times with exponential backoff if there are any errors during the agent invocation.
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def _invoke_agent(agent_executor, prompt_input):
        return agent_executor.invoke(prompt_input)
    
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
    agent = create_tool_calling_agent(data_analyst_llm, tools, prompt_template)
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True, 
        handle_parsing_errors=True,
        robust=True
    )
    
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
    
    try:
        # Hard coded for the POC perscpective, can be enhanced with a database connections or providing user the ability to upload their own dataset in the UI
        df = pd.read_csv("data/marketing_campaign_dataset.csv")

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
        logger.error(f"Could not analyze data with agent. Error: {e}")
        import traceback
        traceback.print_exc()
        data_insights = f"Data analysis unavailable due to error: {str(e)[:200]}"

    # Return only the data insights to be consumed by the next node
    return {"past_campaign_insights": data_insights}


# Search agent: conducts DuckDuckGo searches for market research
def search_agent(queries: list) -> str:
    """Execute search queries and compile results into a single text block."""
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def _search(query: str) -> str:
        return search_tool.invoke(query)
    
    search_tool = DuckDuckGoSearchRun()
    all_results = []
    
    logger.info("Executing search queries...")
    for query in queries:
        try:
            logger.info(f"  Running query: {query}")
            results = _search(query)
            all_results.append(f"--- RESULTS FOR QUERY: {query} ---\n{results}")
        except Exception as e:
            logger.warning(f"Query failed: '{query}'. Error: {e}")
            all_results.append(f"--- SEARCH FAILED FOR QUERY: {query} ---")
    
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
    
    # 1. Generate multiple, targeted search queries <- You can create another agent that can dynamically generate more queries based on the campaign input
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
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _invoke_llm(prompt):
        return llm.invoke(prompt)
    
    try:
        response = _invoke_llm(market_research_prompt)
        content = response.content if hasattr(response, 'content') else response

        if isinstance(content, list) and content and isinstance(content[0], dict) and 'text' in content[0]:
            compiled_trends = content[0]['text']
        else:
            compiled_trends = str(content)
            
        logger.info(f"Successfully synthesized market trends.")
    except Exception as e:
        logger.error(f"Market research synthesis failed: {e}")
        # As a fallback, return the raw (but truncated) search results
        compiled_trends = "Market trend synthesis failed. Raw data follows:\n\n" + search_results_text[:2000]

    return {"market_trends": compiled_trends}

# Third node: Generate the high-level marketing strategy based on the data insights and market trends
def generate_strategy(state: GraphState) -> dict:
    """Generate a structured marketing strategy using the data insights.

    Expects `past_campaign_insights` to be present in the state.
    Returns structured fields that update the state.
    """
    structured_llm = llm.with_structured_output(CampaignStrategy)

    campaign_input = state["campaign_input"]
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _generate_strategy(prompt):
        return structured_llm.invoke(prompt)

    try:
        strategy = _generate_strategy(strategy_prompt)
    except Exception as e:
        logger.error(f"Structured LLM failed: {e}. Falling back to text LLM.")
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

# Fourth node: Recommend specific marketing channels based on the strategy and data insights
def recommend_channels(state: GraphState) -> dict:
    """Recommend specific marketing channels based on data insights and campaign profile.
    
    Uses the data insights and strategy to provide detailed channel recommendations
    with reasoning and expected performance metrics.
    """
    
    structured_llm = llm.with_structured_output(ChannelRecommendation)
    
    strategy = state.get("strategy")
    insights = state.get("past_campaign_insights", "")
    campaign_input = state["campaign_input"]
    
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
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _recommend_channels(prompt):
        return structured_llm.invoke(prompt)

    try:
        recommendation = _recommend_channels(channel_prompt)
        return {"channel_recommendation": recommendation}
    except Exception as e:
        logger.error(f"Channel recommendation failed: {e}")
        return {"channel_recommendation": ChannelRecommendation(
            primary_channels="Unable to generate recommendations",
            channel_rationale=str(e),
            expected_reach="N/A"
        )}

# Fifth node: Optimize the budget allocation across channels and timeline phases
def optimize_budget(state: GraphState) -> dict:
    """Create a detailed budget allocation plan across channels and timeline phases.
    
    Breaks down the campaign budget into specific allocations by channel and
    across different timeline phases, with contingency planning.
    """
    
    structured_llm = llm.with_structured_output(BudgetAllocation)
    
    channel_rec = state.get("channel_recommendation")
    campaign_input = state["campaign_input"]
    
    # Load prompt template and format with variables
    budget_prompt = load_prompt(
        "budget_optimization_prompt",
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
        goals=campaign_input.goals,
        primary_channels=channel_rec.primary_channels if channel_rec else 'N/A',
        channel_rationale=channel_rec.channel_rationale if channel_rec else 'N/A'
    )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _optimize_budget(prompt):
        return structured_llm.invoke(prompt)

    try:
        allocation = _optimize_budget(budget_prompt)
        return {"budget_allocation": allocation}
    except Exception as e:
        logger.error(f"Budget optimization failed: {e}")
        return {"budget_allocation": BudgetAllocation(
            channel_breakdown="Unable to generate breakdown",
            timeline_phases="N/A",
            contingency_plan="N/A"
        )}

# Sixth node: Assess campaign risks and provide mitigation strategies
def assess_risks(state: GraphState) -> dict:
    """Assess campaign risks and provide mitigation strategies.
    
    Identifies potential risks specific to the campaign and provides
    actionable mitigation strategies and success metrics.
    """
    
    structured_llm = llm.with_structured_output(RiskAssessment)
    
    strategy = state.get("strategy")
    budget_alloc = state.get("budget_allocation")
    campaign_input = state["campaign_input"]
    
    # Load prompt template and format with variables
    risk_prompt = load_prompt(
        "risk_assessment_prompt",
        campaign_type=campaign_input.campaign_type,
        target_industry=campaign_input.target_industry,
        target_audience=strategy.target_audience if strategy else 'N/A',
        budget=campaign_input.budget,
        timeline=campaign_input.timeline,
        channel_breakdown=budget_alloc.channel_breakdown if budget_alloc else 'N/A',
        past_campaign_insights=state.get("past_campaign_insights", "N/A")
    )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _assess_risks(prompt):
        return structured_llm.invoke(prompt)

    try:
        assessment = _assess_risks(risk_prompt)
        return {"risk_assessment": assessment}
    except Exception as e:
        print(f"Warning: Risk assessment failed: {e}")
        return {"risk_assessment": RiskAssessment(
            identified_risks="Unable to assess risks",
            mitigation_strategies="N/A",
            success_metrics="N/A"
        )}


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
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _format_report(prompt):
        return llm.invoke(prompt)

    try:
        formatted_md = _format_report(formatting_prompt)
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

    # For UI so that humans can see the whole report and ask further questions or chose to redo analysis
    logger.info("=" * 70)
    logger.info("FORMATTED MARKDOWN REPORT")
    logger.info("=" * 70)
    logger.info(formatted_md[:2000])  # Preview first 2000 chars
    logger.info("\n... (partial report shown above) ...\n")
    logger.info("=" * 70)
    
    approval = 'y'
    # approval = input("\n✓ Save the report to markdown? (yes/no): ").strip().lower()
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
    
    formatted_md = state.get('formatted_markdown', '')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"./outputs/campaign_strategy_{timestamp}.md"
    
    try:
        with open(filename, 'w') as f:
            f.write(formatted_md)
        logger.info(f"Report successfully saved to: {filename}")
        return {"formatted_markdown": filename}
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

    builder.add_edge("generate_strategy", "recommend_channels")
    builder.add_edge("recommend_channels", "optimize_budget")
    builder.add_edge("optimize_budget", "assess_risks")
    builder.add_edge("assess_risks", "format_markdown_report")

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