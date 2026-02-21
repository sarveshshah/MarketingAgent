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
styles_path = Path(__file__).parent / "assets" / "styles.css"
styles = styles_path.read_text(encoding="utf-8")
st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)

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

# Initialize session state for inputs and history
if "history" not in st.session_state:
    st.session_state.history = []
if "campaign_type" not in st.session_state:
    st.session_state.campaign_type = ""
if "target_industry" not in st.session_state:
    st.session_state.target_industry = ""
if "budget_amount" not in st.session_state:
    st.session_state.budget_amount = 0
if "budget_currency" not in st.session_state:
    st.session_state.budget_currency = "$"
if "timeline" not in st.session_state:
    st.session_state.timeline = ""
if "goals" not in st.session_state:
    st.session_state.goals = ""

def apply_selected_preset(preset_options):
    choice = st.session_state.get("preset_choice", "Custom")
    if choice != "Custom":
        for key, value in preset_options[choice].items():
            st.session_state[key] = value

# Function to render the stepper component
def render_stepper(steps, current_key, completed_keys):
    items = []
    for index, (key, label) in enumerate(steps, start=1):
        if key == current_key:
            state = "active"
        elif key in completed_keys:
            state = "complete"
        else:
            state = "pending"
        items.append(
            "<div class=\"step {state}\">"
            "<div class=\"step-circle\">{index}</div>"
            "<div class=\"step-label\">{label}</div>"
            "</div>".format(state=state, index=index, label=label)
        )
    return "<div class=\"stepper\">{items}</div>".format(items="".join(items))

# Utility function to extract and format text from various output structures
def extract_formatted_text(value):
    def format_scalar(item):
        if isinstance(item, str):
            return item.strip()
        if isinstance(item, (int, float, bool)):
            return str(item)
        if isinstance(item, (list, tuple)):
            parts = [str(part).strip() for part in item if str(part).strip()]
            return ", ".join(parts) if parts else None
        return None

    def format_mapping(mapping):
        lines = []
        for key, item in mapping.items():
            formatted = format_scalar(item)
            if not formatted:
                continue
            label = str(key).replace("_", " ").title()
            lines.append(f"- **{label}**: {formatted}")
        return "\n".join(lines) if lines else None

    if hasattr(value, "model_dump"):
        return format_mapping(value.model_dump())
    if hasattr(value, "dict") and callable(value.dict):
        return format_mapping(value.dict())
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    if isinstance(value, dict):
        for key in (
            "formatted_markdown",
            "markdown",
            "content",
            "text",
            "summary",
            "output",
            "report",
            "analysis",
            "insights",
            "recommendation",
            "allocation",
            "risks",
            "strategy",
        ):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text
        if len(value) == 1:
            only_value = next(iter(value.values()))
            formatted = format_scalar(only_value)
            if formatted:
                return formatted
        return format_mapping(value)
    if isinstance(value, (list, tuple)):
        parts = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if parts:
            return "\n\n".join(parts)
    return None

# Add some preset options for quick testing and demonstrations
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
    preset_choice = st.selectbox(
        "Quick preset",
        list(preset_options.keys()),
        key="preset_choice",
        on_change=apply_selected_preset,
        kwargs={"preset_options": preset_options}
    )

    if preset_choice != "Custom":
        st.markdown(
            """
            <div class="card">
                <strong>Preset summary</strong><br/>
                Type: {campaign_type}<br/>
                Industry: {industry}<br/>
                Budget: {budget}<br/>
                Timeline: {timeline}<br/>
                Goals: {goals}
            </div>
            """.format(
                campaign_type=st.session_state.get("campaign_type", ""),
                industry=st.session_state.get("target_industry", ""),
                budget=f"{st.session_state.get('budget_currency', '$')}{st.session_state.get('budget_amount', 0):,}",
                timeline=st.session_state.get("timeline", ""),
                goals=st.session_state.get("goals", "")
            ),
            unsafe_allow_html=True
        )

    st.caption("Fields marked with * are required.")

    with st.form("campaign_form"):
        c_type = st.text_input(
            "Campaign Type *",
            placeholder="e.g., Product Launch, Brand Awareness",
            key="campaign_type"
        )
        c_type_error = st.empty()
        industry = st.text_input(
            "Target Industry *",
            placeholder="e.g., FinTech, Retail, Healthcare",
            key="target_industry"
        )
        industry_error = st.empty()

        col_budget, col_currency = st.columns([2, 1])
        with col_budget:
            budget_amount = st.number_input(
                "Budget Amount *",
                min_value=0,
                step=1000,
                key="budget_amount"
            )
            st.caption("Typical ranges: \$25k-\$250k for mid-size campaigns.")
            budget_error = st.empty()
        with col_currency:
            budget_currency = st.selectbox(
                "Currency",
                options=["$", "€", "£", "₹"],
                key="budget_currency"
            )

        timeline = st.text_input(
            "Timeline",
            placeholder="e.g., Q3 2026, 6 months",
            key="timeline"
        )
        goals = st.text_area(
            "Key Goals",
            placeholder="e.g., Increase leads by 20%, 1M impressions",
            key="goals"
        )

        show_agent_outputs = st.checkbox("Show agent outputs", value=True)
        save_report = st.checkbox("Save report to outputs/", value=True)

        submitted = st.form_submit_button("Generate Strategy")

    if submitted:
        if not c_type:
            c_type_error.caption("Required field.")
        if not industry:
            industry_error.caption("Required field.")
        if not budget_amount:
            budget_error.caption("Required field.")

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
        with st.status("Agents are working...", expanded=True) as status:
            final_markdown = ""
            node_results = {}
            progress = st.progress(0)
            
            # Unified step configuration - Show's thinking process in the UI
            step_config = [
                {"key": "analyze_past_campaigns", "label": "Past Campaigns", "progress": 15, "message": "Analyzing past campaigns data..."},
                {"key": "conduct_market_research", "label": "Market Research", "progress": 35, "message": "Searching the internet for latest market trends..."},
                {"key": "generate_strategy", "label": "Optimal Strategy", "progress": 55, "message": "Synthesizing strategy..."},
                {"key": "recommend_channels", "label": "Top Channels", "progress": 70, "message": "Selecting channels..."},
                {"key": "optimize_budget", "label": "Budget Allocation", "progress": 85, "message": "Allocating budget..."},
                {"key": "assess_risks", "label": "Risks Considerations", "progress": 92, "message": "Assessing risks..."},
                {"key": "format_markdown_report", "label": "Final Report", "progress": 100, "message": "Formatting report..."},
            ]
            
            # Derive steps list for stepper rendering
            steps = [(s["key"], s["label"]) for s in step_config]
            step_updates = {s["key"]: (s["progress"], s["message"]) for s in step_config}
            
            st.markdown("**Progress**")
            stepper_placeholder = st.empty()
            status_line = st.empty()
            completed_steps = set()
            current_step = None
            stepper_placeholder.markdown(
                render_stepper(steps, current_step, completed_steps),
                unsafe_allow_html=True
            )
            status_line.markdown(
                "<div class=\"status-line\">Starting workflow...</div>",
                unsafe_allow_html=True
            )

            def apply_step_update(node_key):
                if node_key not in step_updates:
                    return
                progress_value, message = step_updates[node_key]
                progress.progress(progress_value)
                status_line.markdown(
                    f"<div class=\"status-line\">{message}</div>",
                    unsafe_allow_html=True
                )
                completed_steps.add(node_key)
                stepper_placeholder.markdown(
                    render_stepper(steps, node_key, completed_steps),
                    unsafe_allow_html=True
                )

            # Stream the graph execution
            try:
                for output in app.stream(initial_state):
                    if not output or not isinstance(output, dict):
                        continue

                    for node_name, node_output in output.items():
                        if isinstance(node_output, dict):
                            node_results.update(node_output)

                        # Update status based on the node
                        if node_name == "format_markdown_report":
                            # Capture the final markdown from this node
                            if isinstance(node_output, dict) and "formatted_markdown" in node_output:
                                final_markdown = node_output["formatted_markdown"]

                        if node_name in step_updates:
                            current_step = node_name
                            apply_step_update(node_name)

                status.update(label="Strategy Generated Successfully!", state="complete", expanded=False)
                status_line.markdown(
                    "<div class=\"status-line\">Strategy generated successfully.</div>",
                    unsafe_allow_html=True
                )

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
                report_tab, inputs_tab, outputs_tab = st.tabs(["Report", "Inputs", "Agent Outputs"])

                with report_tab:
                    st.markdown(final_markdown)

                    st.download_button(
                        label="Download Report as Markdown",
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
                                formatted_text = extract_formatted_text(node_results[key])
                                if formatted_text:
                                    st.markdown(f"**{label}**")
                                    st.markdown(formatted_text)
                                else:
                                    st.markdown(f"**{label}**")
                                    st.caption("No formatted text available for this section.")
                    else:
                        available_sections = sum(
                            1 for key in [
                                "past_campaign_insights",
                                "market_trends",
                                "strategy",
                                "channel_recommendation",
                                "budget_allocation",
                                "risk_assessment",
                            ]
                            if node_results.get(key)
                        )
                        st.info(
                            f"Enable 'Show agent outputs' in the form to view intermediate results. "
                            f"({available_sections} sections ready)"
                        )

            except Exception as e:
                status.update(label="Error occurred", state="error")
                st.error(f"An error occurred during execution: {e}")