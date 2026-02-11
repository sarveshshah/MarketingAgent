from dotenv import load_dotenv
from typing import Any, Annotated, Literal, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_community.tools import DuckDuckGoSearchRun
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
import pandas as pd
from datetime import datetime

load_dotenv()

# LLM configurations
llm = ChatGoogleGenerativeAI(
    model="gemini-3-pro-preview", 
    temperature = 0, 
    verbose=True
    )

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

# First node: Collect campaign input from user
def analyze_past_campaigns(state: GraphState) -> dict:
    """Analyze past campaign data and return data-driven insights only.

    This node is responsible solely for extracting data insights from the
    dataset and returning them in the state under `past_campaign_insights`.
    The actual strategy generation is handled by a separate node.
    """

    print("Analyzing past campaign data...")

    campaign_input = state["campaign_input"]

    try:
        df = pd.read_csv("data/marketing_campaign_dataset.csv")
        agent = create_pandas_dataframe_agent(
            llm,
            df,
            verbose = True,
            allow_dangerous_code = True,
            max_iterations = 5
        )

        data_analysis_prompt = f"""
        ### Persona: Expert Marketing Data Analyst

        You are a world-class data analyst with deep expertise in marketing campaign performance. Your sole responsibility is to analyze a pandas DataFrame of historical marketing data to extract actionable, quantitative insights. 
        You must use the provided pandas DataFrame (`df`) to answer the user's questions.

        ### Task & Context

        Your goal is to inform the strategy for an upcoming **{campaign_input.campaign_type}** campaign targeting the **{campaign_input.target_industry}** industry. The insights you provide will be the foundation for all subsequent strategic decisions, including channel selection, budget allocation, and risk assessment. Accuracy and data-driven rigour are paramount.

        ### Analytical Steps & Required Insights

        You MUST perform the following analysis by writing and executing Python code against the `df`. Address each point explicitly in your response:

        1.  **Channel Performance Analysis:**
            *   Calculate the **Conversion Rate** for each marketing channel.
            *   Calculate the **Return on Investment (ROI)** for each channel.
            *   Identify the **top 3 performing channels** based on a combined ranking of ROI and Conversion Rate. Present this as a summary table.

        2.  **Cost Analysis:**
            *   Determine the **average Customer Acquisition Cost (CAC)** for each marketing channel.
            *   Identify the channel with the **lowest CAC**.

        3.  **Audience Demographics:**
            *   Analyze the `Audience` column to identify demographic segments with the **highest conversion rates**.
            *   Provide a list of the top 2-3 audience segments to target.

        4.  **Campaign Duration & Seasonality:**
            *   Calculate the **average and median campaign duration** from the dataset.
            *   Investigate if there are any **seasonality effects** (e.g., specific months or quarters that show higher performance).

        5.  **Campaign Type Effectiveness:**
            *   Analyze the performance of different `Campaign Type` categories in the data.
            *   Identify the **best-performing campaign types** and their typical ROI for the `{campaign_input.target_industry}` sector if possible.

        6.  **Budget Allocation Insights:**
            *   Based on historical ROI and CAC, provide **data-driven recommendations for budget allocation** across the top-performing channels. Frame this as a percentage breakdown (e.g., "Recommend allocating 50% to Channel A, 30% to Channel B...").

        ### Output Requirements

        You MUST structure your final output as a single, comprehensive markdown document. Do not output any other text or explanation before or after the markdown.

        *   **Use clear headings (`##`)** for each section of the analysis (e.g., `## Channel Performance`, `## Cost Analysis`).
        *   **Use tables** to present comparative data (e.g., for channel performance).
        *   **Use bold (`**`)** to highlight key metrics, such as specific ROI percentages, CAC values, and conversion rates.
        *   **Include a concluding "Executive Summary" section** at the top that lists the 3-5 most critical, actionable insights from your analysis in a bulleted list.

        ### Constraints & Best Practices

        *   **NEVER** invent or assume data. All findings must be directly derived from the provided `df`.
        *   Show your work by thinking through the steps, but your final answer must be the formatted markdown report.
        *   Ensure all calculations are accurate.
        *   The response must be a single, valid markdown block.
    """
        # The agent expects a dictionary with an 'input' key.
        agent_response = agent.invoke({"input": data_analysis_prompt})
        # The actual result is in the 'output' key of the response dictionary.
        data_insights = agent_response["output"]

    except Exception as e:
        print(f"Warning: Could not analyze data with agent. Error: {e}")
        data_insights = "Data analysis unavailable due to an error."

    # Return only the data insights to be consumed by the next node
    return {"past_campaign_insights": data_insights}

# Second node: Conduct market research using search queries and synthesize results into market trends
def conduct_market_research(state: GraphState) -> dict:
    """
    Conducts robust market research by running multiple search queries
    and synthesizing the results into a coherent summary of market trends.
    """

    print("Conducting robust market research...")
    campaign_input = state["campaign_input"]
    
    # 1. Generate multiple, targeted search queries
    queries = [
        f"latest marketing trends for {campaign_input.campaign_type} in {campaign_input.target_industry} industry {datetime.now().year}",
        f"consumer behavior trends and preferences in {campaign_input.target_industry} {datetime.now().year}",
        f"successful marketing strategies for {campaign_input.campaign_type} targeting {campaign_input.target_industry}",
        f"emerging marketing channels and technologies for {campaign_input.target_industry}"
    ]
    
    # 2. Execute searches in parallel
    search = DuckDuckGoSearchRun()
    all_results = []
    print("Executing search queries...")
    for query in queries:
        try:
            print(f"  - Running query: {query}")
            results = search.invoke(query)
            all_results.append(f"--- RESULTS FOR QUERY: {query} ---\n{results}")
        except Exception as e:
            print(f"Warning: Query failed: '{query}'. Error: {e}")
            all_results.append(f"--- SEARCH FAILED FOR QUERY: {query} ---")

    # 3. Compile the results with an LLM
    print("Synthesizing market trends from search results...")
    
    search_results_text = "\n\n".join(all_results)
    
    compilation_prompt = f"""
    ### Persona: Expert Market Research Analyst
    You are a professional market research analyst. Your primary skill is synthesizing vast amounts of unstructured text from various sources into a concise, actionable summary of key market trends.

    ### Task & Context
    You have been given the raw, collected results from multiple search queries related to a marketing campaign for a **"{campaign_input.campaign_type}"** in the **"{campaign_input.target_industry}"** industry. 
    Your task is to analyze all this information and distill it into the most important trends for a marketing strategist.

    **Raw Search Results Dump:**
    ```{search_results_text}```
    
    ### Instructions
    1.  **Read and Analyze:** Carefully read through all the provided search results.
    2.  **Identify Key Trends:** Identify the 3-5 most significant and recurring themes or trends that are relevant to the campaign context. Look for patterns related to consumer behavior, technology, channels, and strategy.
    3.  **Summarize and Format:** For each identified trend, write a concise summary. Present your final output as a markdown-formatted bulleted list. Each bullet point should clearly state the trend and briefly explain its implication.

    ### Example Output:
    *   **AI-Driven Personalization:** There is a growing emphasis on using AI to create highly personalized customer experiences across email and web, leading to higher engagement.
    *   **Dominance of Short-Form Video:** Platforms like TikTok and Instagram Reels are critical for reaching younger demographics, with raw, authentic content outperforming polished ads.
    *   **Sustainability as a Brand Differentiator:** Consumers in this industry increasingly prefer brands that demonstrate strong ethical and environmental commitments.

    ### Final Rule:
    Your final output must be **ONLY the markdown bulleted list** summarizing the trends. Do not include any introductory phrases, explanations, or concluding remarks.
    """
    
    try:
        response = llm.invoke(compilation_prompt)
        content = response.content if hasattr(response, 'content') else response

        if isinstance(content, list) and content and isinstance(content[0], dict) and 'text' in content[0]:
            compiled_trends = content[0]['text']
        else:
            compiled_trends = str(content)
            
        print(f"Successfully synthesized market trends.")
    except Exception as e:
        print(f"Warning: Market research synthesis failed: {e}")
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

    strategy_prompt = f"""
    ### Persona: Senior Marketing Strategist

    You are a Senior Marketing Strategist responsible for defining the high-level strategic direction of a new campaign. You have just received a detailed data analysis report and a summary of market trends. Your task is to synthesize this information into a core strategy document.

    ### Context & Data

    1.  **Historical Campaign Analysis (from your data analyst):**
        ```markdown
        {data_insights}
        ```
    2.  **Current Market Trends (from your research team):**
        ```
        {market_trends}
        ```
    3.  **Campaign Mandate:**
        *   **Campaign Type:** {campaign_input.campaign_type}
        *   **Target Industry:** {campaign_input.target_industry}
        *   **Budget:** {campaign_input.budget}
        *   **Timeline:** {campaign_input.timeline}
        *   **Goals:** {campaign_input.goals}

    ### Task & Instructions

    Based *exclusively* on the provided data and campaign mandate, generate a concise, high-level strategy. Your output must be structured according to the `CampaignStrategy` format.

    1.  **`target_audience`**: Synthesize the "Audience Demographics" from the data analysis to create a specific, descriptive persona. Go beyond a simple demographic list; create a narrative description (e.g., "Tech-savvy millennials in urban areas who value sustainability...").
    2.  **`campaign_channels`**: Based on the "Channel Performance Analysis" (ROI, Conversion Rate), list the top 2-3 most promising channels as a comma-separated string.
    3.  **`acquisition_cost_estimate`**: Using the "Cost Analysis" data, provide a realistic estimated range for Customer Acquisition Cost (CAC) for the recommended channels.
    4.  **`expected_roi`**: Based on historical "ROI" data for similar campaigns and channels, provide a specific, quantifiable ROI estimate or range.

    ### Constraints & Best Practices

    *   **Data-Driven:** Every field in your output must be directly justified by the `data_insights` or `market_trends` provided. Do not invent information.
    *   **Reference Your Sources:** Briefly mention which data point informs your conclusion (e.g., "Targeting millennials based on the high conversion rates reported in the analysis.").
    *   **Be Concise:** Keep descriptions brief and to the point.
    *   **Output ONLY the structured data.** Your response will be parsed automatically.
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
    
    channel_prompt = f"""
    ### Persona: Digital Marketing Channel Specialist

    You are a specialist in digital marketing channel strategy. You have been given a high-level strategy and a comprehensive data analysis report. Your task is to provide a detailed and actionable channel recommendation.

    ### Context & Data

    1.  **Data Analysis Report:**
        ```markdown
        {insights}
        ```
    2.  **Approved High-Level Strategy:**
        *   **Target Audience:** {strategy.target_audience if strategy else 'N/A'}
        *   **Selected Channels (High-Level):** {strategy.campaign_channels if strategy else 'N/A'}
        *   **Campaign Type:** {campaign_input.campaign_type}
        *   **Industry:** {campaign_input.target_industry}
        *   **Budget:** {campaign_input.budget}
        *   **Timeline:** {campaign_input.timeline}

    ### Task & Instructions

    Your task is to elaborate on the high-level strategy by providing a detailed recommendation for the top marketing channels. Your output must conform to the `ChannelRecommendation` structure.

    1.  **`primary_channels`**: List the top 2-3 marketing channels. For each channel, recommend a specific budget percentage allocation. This must be a single string (e.g., "Email Marketing (40%), LinkedIn Ads (35%), Google Search (25%)"). The allocation should be directly informed by the ROI and CAC data in the analysis.
    2.  **`channel_rationale`**: For each recommended channel, provide a concise, data-driven justification. Reference specific metrics from the `insights` (e.g., "LinkedIn Ads are recommended due to its **12% conversion rate** with the target demographic, as noted in the analysis.").
    3.  **`expected_reach`**: For each channel, provide a *quantifiable* estimate of reach, engagement, or other relevant KPIs. Base these estimates on the historical data provided in the `insights`.

    ### Constraints & Best Practices

    *   **Be Specific and Quantitative:** Avoid vague statements. Use the numbers from the data analysis.
    *   **Justify Everything:** Explicitly link your recommendations back to the provided `insights`.
    *   **Align with Strategy:** Ensure your channel choices and rationale align perfectly with the `target_audience` defined in the strategy.
    *   **Output ONLY the structured data.**
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

# Fifth node: Optimize the budget allocation across channels and timeline phases
def optimize_budget(state: GraphState) -> dict:
    """Create a detailed budget allocation plan across channels and timeline phases.
    
    Breaks down the campaign budget into specific allocations by channel and
    across different timeline phases, with contingency planning.
    """
    
    structured_llm = llm.with_structured_output(BudgetAllocation)
    
    channel_rec = state.get("channel_recommendation")
    campaign_input = state["campaign_input"]
    
    budget_prompt = f"""
    ### Persona: Marketing Operations & Finance Analyst

    You are a meticulous financial analyst specializing in marketing budget optimization. You have been provided with the campaign's channel strategy and overall budget. Your task is to create a detailed, phased budget plan.

    ### Context & Data

    1.  **Campaign Mandate:**
        *   **Total Budget:** {campaign_input.budget}
        *   **Timeline:** {campaign_input.timeline}
        *   **Goals:** {campaign_input.goals}
    2.  **Approved Channel Strategy:**
        *   **Recommended Channels & Allocation:** {channel_rec.primary_channels if channel_rec else 'N/A'}
        *   **Channel Rationale:** {channel_rec.channel_rationale if channel_rec else 'N/A'}

    ### Task & Instructions

    Create a detailed budget allocation plan that breaks down the total budget across channels and time. Your output must conform to the `BudgetAllocation` structure.

    1.  **`channel_breakdown`**: Confirm and list the final budget allocation percentages per channel as a single string. This should match the input from the channel strategist (e.g., "Email: 40%, LinkedIn Ads: 35%, Google Search: 25%").
    2.  **`timeline_phases`**: Divide the campaign `timeline` into logical phases (e.g., "Month 1-2: Awareness", "Month 3-5: Conversion", "Month 6: Optimization"). Allocate a percentage of the *total budget* to each phase. This should be a single string.
    3.  **`contingency_plan`**: Recommend a specific percentage of the total budget to be held in reserve as a contingency fund. Provide a brief justification (e.g., "A 10% contingency fund is recommended to address unforeseen opportunities or underperforming channels.").

    ### Constraints & Best Practices

    *   **Mathematical Accuracy:** Ensure all percentages in `channel_breakdown` and `timeline_phases` add up to 100% (excluding the contingency).
    *   **Logical Phasing:** The timeline phases should be logical for the campaign type and duration.
    *   **Clarity and Conciseness:** Present the information clearly and without unnecessary jargon.
    *   **Output ONLY the structured data.**
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
    
    risk_prompt = f"""
    ### Persona: Senior Marketing Risk Analyst

    You are a seasoned risk management consultant with a specialization in marketing campaigns. You have been given the complete campaign strategy. Your task is to identify potential risks and develop a proactive plan to manage them.

    ### Context & Data

    **Complete Campaign Plan:**
    *   **Campaign Type:** {campaign_input.campaign_type}
    *   **Target Industry:** {campaign_input.target_industry}
    *   **Target Audience:** {strategy.target_audience if strategy else 'N/A'}
    *   **Budget:** {campaign_input.budget}
    *   **Timeline:** {campaign_input.timeline}
    *   **Channels & Budgeting:** {budget_alloc.channel_breakdown if budget_alloc else 'N/A'}
    *   **Historical Data Insights:** {state.get("past_campaign_insights", "N/A")}

    ### Task & Instructions

    Identify potential risks and prepare a mitigation plan. Your output must conform to the `RiskAssessment` structure.

    1.  **`identified_risks`**: Identify the top 3-5 potential risks specific to this campaign. For each risk, provide a brief description and rank its severity (e.g., "High: Key channel underperforms ROI target," "Medium: Competitor launches a similar campaign," "Low: Negative social media sentiment.").
    2.  **`mitigation_strategies`**: For each identified risk, propose a concrete, actionable mitigation strategy. What steps will you take if the risk materializes? (e.g., "For underperforming channels, reallocate budget to the next best performing channel within 2 weeks.").
    3.  **`success_metrics`**: For each risk, define the specific Key Performance Indicator (KPI) or metric that will be used to monitor it. These are your early warning indicators (e.g., "Weekly review of channel ROI and CAC against benchmarks from data analysis.").

    ### Constraints & Best Practices

    *   **Be Specific, Not Generic:** Risks should be tailored to this campaign (e.g., instead of "Bad PR," use "Negative reviews from tech influencers about the new phone's battery life.").
    *   **Action-Oriented:** Mitigation strategies should be practical and executable.
    *   **Data-Informed:** Where possible, use the historical data to inform potential risks (e.g., "Risk of high CAC on social media, as seen in previous campaigns.").
    *   **Output ONLY the structured data.**
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

# Initial node: Collect campaign input from user
def collect_campaign_input(state: GraphState) -> dict:
    """Collect marketing campaign information from user"""
    
    # For easy testing purposes
    campaign_input = {
        "campaign_type": "New Phone Launch",
        "target_industry": "High income earners",
        "budget": "100000",
        "timeline": "6 months",
        "goals": "Maximum engagement"
    }
    
    # print("\n=== Marketing Campaign Input ===\n")

    # campaign_input = {
    #     "campaign_type": input("Campaign type (e.g., product launch, brand awareness, retention): ").strip(),
    #     "target_industry": input("Target industry or market segment: ").strip(),
    #     "budget": input("Budget allocated for campaign: ").strip(),
    #     "timeline": input("Timeline for campaign (e.g., 3 months, Q1 2026): ").strip(),
    #     "goals": input("Specific goals or KPIs (comma-separated): ").strip(),
    # }
    
    return {"campaign_input": CampaignInput(**campaign_input)}

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
    
    formatting_prompt = f"""
    ### Persona: Executive Communications Expert & Designer

    You are an expert in creating high-impact business reports for executive audiences. You specialize in transforming raw data and strategic points into a polished, professional, and visually appealing markdown document.

    ### Task & Context

    You have been given all the final components of a marketing strategy, generated by a team of specialists. Your task is to assemble these components into a single, cohesive, and beautifully formatted markdown report. This report will be presented to senior leadership.

    ### Raw Report Components:

    **1. Campaign Overview:**
    *   **Type:** {campaign_input.campaign_type}
    *   **Industry:** {campaign_input.target_industry}
    *   **Budget:** {campaign_input.budget}
    *   **Timeline:** {campaign_input.timeline}
    *   **Goals:** {campaign_input.goals}

    **2. Data Insights & Market Trends:**
    *   **Historical Analysis Summary:** {state.get("past_campaign_insights", "N/A")}
    *   **Market Trends Summary:** {state.get("market_trends", "N/A")}

    **3. Core Strategy:**
    *   **Target Audience:** {strategy.target_audience if strategy else 'N/A'}
    *   **Key Channels:** {strategy.campaign_channels if strategy else 'N/A'}
    *   **Estimated CAC:** {strategy.acquisition_cost_estimate if strategy else 'N/A'}
    *   **Expected ROI:** {strategy.expected_roi if strategy else 'N/A'}

    **4. Detailed Channel Plan:**
    *   **Primary Channels & Budget %:** {channels.primary_channels if channels else 'N/A'}
    *   **Rationale:** {channels.channel_rationale if channels else 'N/A'}
    *   **Expected Reach/KPIs:** {channels.expected_reach if channels else 'N/A'}

    **5. Budget & Timeline:**
    *   **Channel Breakdown:** {budget.channel_breakdown if budget else 'N/A'}
    *   **Phasing:** {budget.timeline_phases if budget else 'N/A'}
    *   **Contingency:** {budget.contingency_plan if budget else 'N/A'}

    **6. Risk Management Plan:**
    *   **Identified Risks:** {risks.identified_risks if risks else 'N/A'}
    *   **Mitigation Strategies:** {risks.mitigation_strategies if risks else 'N/A'}
    *   **Monitoring KPIs:** {risks.success_metrics if risks else 'N/A'}

    ### Output Requirements

    Produce a single, elegant markdown report. Your output must be **ONLY the markdown code**.

    *   **Structure:**
        1.  **Title:** Start with a `# Marketing Strategy:` followed by the campaign type.
        2.  **Executive Summary:** A short, impactful summary (2-3 sentences) of the campaign's goal and expected outcome.
        3.  **Campaign Overview:** Use a markdown table to present the overview details.
        4.  **Strategic Foundation:** Create a section that includes `## Data-Driven Insights` and `## Market Trends`, summarizing the key inputs.
        5.  **Core Strategy:** Create a `## Recommended Strategy` section with clear sub-headings (`### Target Audience`, `### Core Channels`, etc.).
        6.  **Execution Plan:** Create a `## Execution Plan` section with `### Channel & Budget Allocation` and `### Phased Timeline` sub-headings. Use tables for clarity.
        7.  **Risk Management:** Create a final `## Risk & Mitigation Plan` section, using a table to lay out risks, mitigation steps, and KPIs.
    *   **Formatting:**
        *   Use headings (`#`, `##`, `###`) to create a clear hierarchy.
        *   Use bold (`**`) and italics (`*`) to emphasize key terms, metrics, and takeaways.
        *   Use bullet points (`*`) for lists.
        *   Use tables for structured data to improve readability.

    ### Final Instruction:
    Review all the provided components and synthesize them into a single, polished, and professional report. Return **ONLY** the markdown. Do not include any other commentary.
    """
    
    try:
        formatted_md = llm.invoke(formatting_prompt)
        content = formatted_md.content if hasattr(formatted_md, 'content') else formatted_md
        
        if isinstance(content, list) and content and isinstance(content[0], dict) and 'text' in content[0]:
            formatted_content = content[0]['text']
        else:
            formatted_content = str(content)

        return {"formatted_markdown": formatted_content}
    except Exception as e:
        print(f"Warning: Markdown formatting failed: {e}")
        # Fallback to basic structure
        return {"formatted_markdown": generate_fallback_report(state)}

# Final node: Ask for human approval before saving the markdown report to a file
def human_approval_step(state: GraphState) -> dict:
    """Ask user to review and approve the markdown before saving.
    
    Displays the formatted markdown and waits for user confirmation.
    """

    formatted_md = state.get('formatted_markdown', '')

    # For UI so that humans can see the whole report and ask further questions or chose to redo analysis
    
    print("\n" + "="*70)
    print("FORMATTED MARKDOWN REPORT")
    print("="*70)
    print(formatted_md[:2000])  # Preview first 2000 chars
    print("\n... (partial report shown above) ...\n")
    
    print("="*70)
    
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
        print("\nReport NOT saved. No confirmation received.")
        return {"formatted_markdown": ""}  # Clear from state
    
    formatted_md = state.get('formatted_markdown', '')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"campaign_strategy_{timestamp}.md"
    
    try:
        with open(filename, 'w') as f:
            f.write(formatted_md)
        print(f"\nReport successfully saved to: {filename}")
        return {"formatted_markdown": filename}
    except Exception as e:
        print(f"Error saving file: {e}")
        return {"formatted_markdown": ""}

# Build the graph
builder = StateGraph(GraphState)
builder.add_node("collect_campaign_input", collect_campaign_input)
builder.add_node("analyze_past_campaigns", analyze_past_campaigns)
builder.add_node("conduct_market_research", conduct_market_research)
builder.add_node("generate_strategy", generate_strategy)
builder.add_node("recommend_channels", recommend_channels)
builder.add_node("optimize_budget", optimize_budget)
builder.add_node("assess_risks", assess_risks)
builder.add_node("format_markdown_report", format_markdown_report)
builder.add_node("human_approval_step", human_approval_step)
builder.add_node("save_approved_markdown", save_approved_markdown)

builder.add_edge(START, "collect_campaign_input")
builder.add_edge("collect_campaign_input", "analyze_past_campaigns")
builder.add_edge("analyze_past_campaigns", "conduct_market_research")
builder.add_edge("conduct_market_research", "generate_strategy")
builder.add_edge("generate_strategy", "recommend_channels")
builder.add_edge("recommend_channels", "optimize_budget")
builder.add_edge("optimize_budget", "assess_risks")
builder.add_edge("assess_risks", "format_markdown_report")
builder.add_edge("format_markdown_report", "human_approval_step")
builder.add_edge("human_approval_step", "save_approved_markdown")
builder.add_edge("save_approved_markdown", END)

app = builder.compile()

# Prepare initial state with both input and placeholder values for output fields
initial_state = {
    "campaign_input": None,
    "past_campaign_insights": "",
    "market_trends": "",
    "strategy": None,
    "channel_recommendation": None,
    "budget_allocation": None,
    "risk_assessment": None,
    "formatted_markdown": None,
    "human_approval": False
}

# Run graph with user-provided campaign input
print("\nAnalyzing campaign requirements...")
result = app.invoke(initial_state)