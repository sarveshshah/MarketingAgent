import streamlit as st
from datetime import datetime
from pathlib import Path
from main import build_graph, CampaignInput

app = build_graph(include_human_approval=False).compile()

# Page Configuration
st.set_page_config(
    page_title="Agentic Marketing Strategist",
    page_icon="🚀",
    layout="wide"
)

# Custom CSS for a cleaner look
st.markdown("""
<style>
    :root {
        --accent: #ff6b35;
        --ink: #1d1d1f;
        --muted: #6b7280;
        --panel: #f8fafc;
        --stroke: #e5e7eb;
    }
    .stButton>button {
        width: 100%;
        background-color: var(--accent);
        color: white;
        border: 1px solid var(--accent);
    }
    .hero {
        padding: 18px 20px;
        background: linear-gradient(135deg, #fff3e9, #fffaf2);
        border: 1px solid var(--stroke);
        border-radius: 14px;
    }
    .hero h1 {
        color: var(--ink);
        margin-bottom: 6px;
    }
    .hero p {
        color: var(--muted);
        margin: 0;
    }
    .card {
        background-color: var(--panel);
        border: 1px solid var(--stroke);
        padding: 14px 16px;
        border-radius: 12px;
    }
    .pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        background: #fff1e6;
        color: #7a2e0e;
        border: 1px solid #ffd9c2;
        font-size: 12px;
        margin-right: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown(
    """
    <div class="hero">
        <div class="pill">Agentic workflow</div>
        <div class="pill">Data-driven</div>
        <div class="pill">Fast iterations</div>
        <h1>🚀 Agentic Marketing Strategist</h1>
        <p>Generate comprehensive, data-driven marketing strategies powered by AI agents.</p>
    </div>
    """,
    unsafe_allow_html=True
)

if "history" not in st.session_state:
    st.session_state.history = []

preset_options = {
    "Custom": {},
    "Product Launch": {
        "campaign_type": "Product Launch",
        "target_industry": "Consumer Electronics",
        "budget_amount": 150000,
        "budget_currency": "$",
        "timeline": "Q3 2026",
        "goals": "Build awareness, 3% CTR, 1M impressions"
    },
    "Brand Awareness": {
        "campaign_type": "Brand Awareness",
        "target_industry": "Retail",
        "budget_amount": 90000,
        "budget_currency": "$",
        "timeline": "6 months",
        "goals": "Increase share of voice, improve recall by 10%"
    },
    "B2B Lead Gen": {
        "campaign_type": "Lead Generation",
        "target_industry": "SaaS",
        "budget_amount": 120000,
        "budget_currency": "$",
        "timeline": "4 months",
        "goals": "500 MQLs, CPL under $180"
    }
}

# Layout: Sidebar for Inputs, Main Area for Results
with st.sidebar:
    st.header("Campaign Details")
    preset_choice = st.selectbox("Quick preset", list(preset_options.keys()))
    if st.button("Apply preset") and preset_choice != "Custom":
        for key, value in preset_options[preset_choice].items():
            st.session_state[key] = value

    st.caption("Fields marked with * are required.")

    with st.form("campaign_form"):
        c_type = st.text_input(
            "Campaign Type *",
            placeholder="e.g., Product Launch, Brand Awareness",
            value=st.session_state.get("campaign_type", ""),
            key="campaign_type"
        )
        industry = st.text_input(
            "Target Industry *",
            placeholder="e.g., FinTech, Retail, Healthcare",
            value=st.session_state.get("target_industry", ""),
            key="target_industry"
        )

        col_budget, col_currency = st.columns([2, 1])
        with col_budget:
            budget_amount = st.number_input(
                "Budget Amount *",
                min_value=0,
                step=1000,
                value=int(st.session_state.get("budget_amount", 0)),
                key="budget_amount"
            )
        with col_currency:
            budget_currency = st.selectbox(
                "Currency",
                options=["$", "€", "£", "₹"],
                index=["$", "€", "£", "₹"].index(st.session_state.get("budget_currency", "$")),
                key="budget_currency"
            )

        timeline = st.text_input(
            "Timeline",
            placeholder="e.g., Q3 2026, 6 months",
            value=st.session_state.get("timeline", ""),
            key="timeline"
        )
        goals = st.text_area(
            "Key Goals",
            placeholder="e.g., Increase leads by 20%, 1M impressions",
            value=st.session_state.get("goals", ""),
            key="goals"
        )

        show_agent_outputs = st.checkbox("Show agent outputs", value=False)
        save_report = st.checkbox("Save report to outputs/", value=True)

        submitted = st.form_submit_button("Generate Strategy")

if submitted:
    if not (c_type and industry and budget_amount):
        st.error("Please fill in the required fields (Type, Industry, Budget).")
    else:
        budget_display = f"{budget_currency}{budget_amount:,.0f}"

        # Create the input object
        user_input = CampaignInput(
            campaign_type=c_type,
            target_industry=industry,
            budget=budget_display,
            timeline=timeline,
            goals=goals
        )
        
        # Initial State
        initial_state = {"campaign_input": user_input}
        
        # Main Content Area
        st.subheader("Agent Workflow")

        # Container for the "Thinking Process"
        with st.status("🤖 Agents are working...", expanded=True) as status:
            final_markdown = ""
            node_results = {}
            progress = st.progress(0)

            # Stream the graph execution
            try:
                for output in app.stream(initial_state):
                    if not output or not isinstance(output, dict):
                        continue

                    for node_name, node_output in output.items():
                        if isinstance(node_output, dict):
                            node_results.update(node_output)

                        # Update status based on the node
                        if node_name == "analyze_past_campaigns":
                            st.write("📊 Analyzing historical campaign data...")
                            progress.progress(15)
                        elif node_name == "conduct_market_research":
                            st.write("🌍 Conducting market research & trend analysis...")
                            progress.progress(35)
                        elif node_name == "generate_strategy":
                            st.write("🧠 Synthesizing high-level strategy...")
                            progress.progress(55)
                        elif node_name == "recommend_channels":
                            st.write("📢 Identifying optimal channels...")
                            progress.progress(70)
                        elif node_name == "optimize_budget":
                            st.write("💰 Allocating budget resources...")
                            progress.progress(85)
                        elif node_name == "assess_risks":
                            st.write("🛡️ Assessing potential risks...")
                            progress.progress(92)
                        elif node_name == "format_markdown_report":
                            st.write("📝 Formatting final report...")
                            # Capture the final markdown from this node
                            if isinstance(node_output, dict) and "formatted_markdown" in node_output:
                                final_markdown = node_output["formatted_markdown"]
                            progress.progress(100)

                status.update(label="Strategy Generated Successfully!", state="complete", expanded=False)

                if not final_markdown:
                    raise ValueError("No final markdown returned from the graph.")

                st.session_state.history.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "industry": industry,
                    "campaign_type": c_type,
                    "markdown": final_markdown
                })

                # Display the Result
                st.divider()
                report_tab, inputs_tab, outputs_tab = st.tabs(["📄 Report", "📥 Inputs", "🧩 Agent Outputs"])

                with report_tab:
                    st.markdown(final_markdown)

                    st.download_button(
                        label="📥 Download Report as Markdown",
                        data=final_markdown,
                        file_name=f"marketing_strategy_{industry.replace(' ', '_')}.md",
                        mime="text/markdown"
                    )

                    if save_report:
                        outputs_dir = Path("outputs")
                        outputs_dir.mkdir(parents=True, exist_ok=True)
                        file_path = outputs_dir / f"campaign_strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                        file_path.write_text(final_markdown, encoding="utf-8")
                        st.success(f"Saved report to {file_path}")

                with inputs_tab:
                    st.markdown("""
                    <div class="card">
                        <strong>Campaign Summary</strong><br/>
                        Type: {campaign_type}<br/>
                        Industry: {industry}<br/>
                        Budget: {budget}<br/>
                        Timeline: {timeline}<br/>
                        Goals: {goals}
                    </div>
                    """.format(
                        campaign_type=c_type,
                        industry=industry,
                        budget=budget_display,
                        timeline=timeline or "Not specified",
                        goals=goals or "Not specified"
                    ), unsafe_allow_html=True)

                with outputs_tab:
                    if show_agent_outputs:
                        st.subheader("Agent Output Snapshot")
                        for label, key in [
                            ("Past Campaign Insights", "past_campaign_insights"),
                            ("Market Trends", "market_trends"),
                            ("Strategy", "strategy"),
                            ("Channel Recommendations", "channel_recommendation"),
                            ("Budget Allocation", "budget_allocation"),
                            ("Risk Assessment", "risk_assessment"),
                        ]:
                            if key in node_results and node_results[key]:
                                st.markdown(f"**{label}**")
                                st.write(node_results[key])
                    else:
                        st.info("Enable 'Show agent outputs' in the form to view intermediate results.")

            except Exception as e:
                status.update(label="Error occurred", state="error")
                st.error(f"An error occurred during execution: {e}")