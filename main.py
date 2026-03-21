"""MarketingAgent CLI entry point.

This module re-exports key symbols for backward compatibility and provides
the interactive ``main()`` function.  All heavy lifting lives in the
dedicated sub-modules (config, models, llm, agents, nodes, graph).
"""

from config import settings, logger                          # noqa: F401
from models import CampaignInput                             # noqa: F401
from llm import _get_llm                                     # noqa: F401
from graph import build_graph, run_campaign                  # noqa: F401


def main() -> None:
    """Main function to run the LangGraph."""
    logger.info("Starting LangGraph execution...")
    app = build_graph(include_human_approval=True).compile()

    initial_state = {"campaign_input": None}

    logger.info("Analyzing campaign requirements...")
    app.invoke(initial_state)
    logger.info("Campaign analysis complete.")


if __name__ == "__main__":
    main()