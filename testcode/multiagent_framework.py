"""
Multiagent Framework using LangChain and LangGraph

This script defines a multiagent framework with three nodes:
1. Analyst: Reads CSV files, calculates metrics, and generates insights.
2. Campaign Drafter: Drafts a marketing campaign based on insights from the Analyst.
3. Critique Strategist: Reviews and finalizes the marketing campaign.

State is passed between nodes using LangGraph's state management capabilities.
"""

from langchain.agents import Tool, initialize_agent
from langchain.llms import GoogleGemini
from langgraph import Node, Graph
import os
import pandas as pd

# Initialize the LLM with Google Gemini API key
llm = GoogleGemini(model="2.5-flash", api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

# Define Node 1: Analyst
class Analyst(Node):
    def __init__(self):
        super().__init__(name="Analyst")

    def available_files(self):
        """List available CSV files in the data folder."""
        data_folder = "data"
        return [f for f in os.listdir(data_folder) if f.endswith(".csv")]

    def calculate_metrics(self, file_name):
        """Read a CSV file and calculate metrics."""
        file_path = os.path.join("data", file_name)
        df = pd.read_csv(file_path)
        metrics = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
        }
        return metrics

    def run(self, state):
        """Run the Analyst node."""
        files = self.available_files()
        if not files:
            raise ValueError("No CSV files found in the data folder.")

        # For simplicity, use the first file
        selected_file = files[0]
        metrics = self.calculate_metrics(selected_file)
        state["insights"] = metrics
        return state

# Define Node 2: Campaign Drafter
class CampaignDrafter(Node):
    def __init__(self):
        super().__init__(name="Campaign Drafter")

    def draft_campaign(self, insights):
        """Draft a marketing campaign based on insights."""
        prompt = f"Draft a marketing campaign based on the following insights: {insights}"
        return llm(prompt)

    def run(self, state):
        """Run the Campaign Drafter node."""
        insights = state.get("insights")
        if not insights:
            raise ValueError("No insights found in state.")

        campaign = self.draft_campaign(insights)
        state["draft_campaign"] = campaign
        return state

# Define Node 3: Critique Strategist
class CritiqueStrategist(Node):
    def __init__(self):
        super().__init__(name="Critique Strategist")

    def critique_campaign(self, draft):
        """Critique and finalize the marketing campaign."""
        prompt = f"Critique and finalize the following marketing campaign: {draft}"
        return llm(prompt)

    def run(self, state):
        """Run the Critique Strategist node."""
        draft = state.get("draft_campaign")
        if not draft:
            raise ValueError("No draft campaign found in state.")

        finalized_campaign = self.critique_campaign(draft)
        state["finalized_campaign"] = finalized_campaign
        return state

# Build the Graph
analyst = Analyst()
campaign_drafter = CampaignDrafter()
critique_strategist = CritiqueStrategist()

graph = Graph()
graph.add_node(analyst)
graph.add_node(campaign_drafter)
graph.add_node(critique_strategist)

graph.add_edge(analyst, campaign_drafter)
graph.add_edge(campaign_drafter, critique_strategist)

# Run the Graph
if __name__ == "__main__":
    state = {}
    state = graph.run(state)

    # Output the final result
    print("Finalized Campaign:")
    print(state.get("finalized_campaign"))