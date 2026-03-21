"""Reusable agents: data-analysis (Python REPL) and web search."""

import io

import pandas as pd
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun

from marketing_agent.config import logger, standard_retry, fast_retry
from marketing_agent.llm import _get_analyst_llm, _get_search_llm, load_prompt, _extract_text
from marketing_agent.guardrails import SafePythonREPLTool, InjectionDetector


# ---------------------------------------------------------------------------
# Data-analysis agent
# ---------------------------------------------------------------------------

def data_analysis_agent(df: pd.DataFrame, analysis_prompt: str) -> str:
    """Data analysis agent that uses a Python REPL tool to analyze the dataframe and extract insights."""

    tools = [SafePythonREPLTool(dataframe=df)]

    # Construct a prompt that includes the dataframe schema
    buffer = io.StringIO()
    df.info(buf=buffer)
    df_info = buffer.getvalue()
    df_preview = df.head().to_string()

    system_message = load_prompt(
        "_system_data_analysis_prompt",
        df_info=df_info,
        df_preview=df_preview,
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(_get_analyst_llm(), tools, prompt_template)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_execution_time=300,  # 5-minute hard cap to prevent hangs
    )

    @standard_retry
    def _invoke_agent(executor, prompt_input):
        return executor.invoke(prompt_input)

    agent_response = _invoke_agent(agent_executor, {"input": analysis_prompt})
    return agent_response["output"]


# ---------------------------------------------------------------------------
# Search agent
# ---------------------------------------------------------------------------

def search_agent(queries: list) -> str:
    """Execute search queries using Gemini Google Search (primary) or DuckDuckGo (fallback)."""

    gemini_search_llm = _get_search_llm()
    has_gemini_search = gemini_search_llm is not None
    ddg_tool = DuckDuckGoSearchRun()

    @fast_retry
    def _search_google(query: str) -> str:
        response = gemini_search_llm.invoke(f"Perform a comprehensive Google search and summarize the findings for: {query}")
        return _extract_text(response.content)

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
                continue
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

    # Scan search results for embedded injection payloads
    _search_detector = InjectionDetector(use_llm=False)
    search_results_text = _search_detector.scan_search_results(search_results_text)

    return search_results_text
