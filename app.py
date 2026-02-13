import streamlit as st
import pandas as pd
from main import app, CampaignInput

# Page Configuration
st.set_page_config(
    page_title="Agentic Marketing Strategist",
    page_icon="🚀",
    layout="wide"
)

# Custom CSS for a cleaner look
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
    }
    .report-view {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("🚀 Agentic Marketing Strategist")
st.markdown("Generate comprehensive, data-driven marketing strategies powered by AI agents.")

# Layout: Sidebar for Inputs, Main Area for Results
with st.sidebar:
    st.header("Campaign Details")
    
    with st.form("campaign_form"):
        c_type = st.text_input("Campaign Type", placeholder="e.g., Product Launch, Brand Awareness")
        industry = st.text_input("Target Industry", placeholder="e.g., FinTech, Retail, Healthcare")
        budget = st.text_input("Budget", placeholder="e.g., $50,000")
        timeline = st.text_input("Timeline", placeholder="e.g., Q3 2024, 6 months")
        goals = st.text_area("Key Goals", placeholder="e.g., Increase leads by 20%, 1M impressions")
        
        submitted = st.form_submit_button("Generate Strategy")

if submitted:
    if not (c_type and industry and budget):
        st.error("Please fill in the required fields (Type, Industry, Budget).")
    else:
        # Create the input object
        user_input = CampaignInput(
            campaign_type=c_type,
            target_industry=industry,
            budget=budget,
            timeline=timeline,
            goals=goals
        )
        
        # Initial State
        initial_state = {"campaign_input": user_input}
        
        # Main Content Area
        st.subheader("Agent Workflow")
        
        # Container for the "Thinking Process"
        with st.status("🤖 Agents are working...", expanded=True) as status:
            final_state = None
            
            # Stream the graph execution
            try:
                for output in app.stream(initial_state):
                    for node_name, node_output in output.items():
                        # Update status based on the node
                        if node_name == "analyze_past_campaigns":
                            st.write("📊 Analyzing historical campaign data...")
                        elif node_name == "conduct_market_research":
                            st.write("🌍 Conducting market research & trend analysis...")
                        elif node_name == "generate_strategy":
                            st.write("🧠 Synthesizing high-level strategy...")
                        elif node_name == "recommend_channels":
                            st.write("📢 Identifying optimal channels...")
                        elif node_name == "optimize_budget":
                            st.write("💰 Allocating budget resources...")
                        elif node_name == "assess_risks":
                            st.write("🛡️ Assessing potential risks...")
                        elif node_name == "format_markdown_report":
                            st.write("📝 Formatting final report...")
                            # Capture the final markdown from this node
                            if "formatted_markdown" in node_output:
                                final_markdown = node_output["formatted_markdown"]
                
                status.update(label="Strategy Generated Successfully!", state="complete", expanded=False)
                
                # Display the Result
                st.divider()
                st.subheader("📄 Strategic Report")
                st.markdown(final_markdown)
                
                # Export Button
                st.download_button(
                    label="📥 Download Report as Markdown",
                    data=final_markdown,
                    file_name=f"marketing_strategy_{industry.replace(' ', '_')}.md",
                    mime="text/markdown"
                )
                
            except Exception as e:
                status.update(label="Error occurred", state="error")
                st.error(f"An error occurred during execution: {e}")