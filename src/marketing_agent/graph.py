"""LangGraph pipeline construction and execution helpers."""

from langgraph.graph import StateGraph, START, END

from marketing_agent.models import CampaignInput, GraphState
from marketing_agent.nodes import (
    collect_campaign_input,
    analyze_past_campaigns,
    conduct_market_research,
    generate_strategy,
    recommend_channels,
    optimize_budget,
    assess_risks,
    format_markdown_report,
    human_approval_step,
    save_approved_markdown,
)


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
    builder.add_edge("assess_risks", "wait_for_budget")

    # Static Fan-In: both paths are exactly 2 nodes deep.
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
