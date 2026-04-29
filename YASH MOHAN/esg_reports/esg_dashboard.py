import json
import os
import streamlit as st
import altair as alt
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

# Import Graph and Helper
# We need to make sure src is in pythonpath if running from root
import sys
if "." not in sys.path:
    sys.path.append(".")

from src.graph.workflow import build_esg_graph
from src.embeddings.local_store import LocalVectorStore
from src.utils.report_generator import create_pdf

# -----------------------------------------------------------------------------
# Configuration & Setup
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="ESG Analyser (LangGraph)",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Resolve repository root
REPO_ROOT = Path(__file__).resolve().parent
PARSED = REPO_ROOT / "data" / "processed" / "parsed_structured.json"
METRICS = REPO_ROOT / "data" / "processed" / "metrics.json"
VECTOR_STORE_PATH = Path("data/processed/vector_store.json")

# -----------------------------------------------------------------------------
# Custom CSS
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Outfit', sans-serif;
        color: #1a3c34;
    }
    
    .stApp {
        background-color: #f4f6f8;
    }
    
    /* Custom Card Style for Metrics */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e1e4e8;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: #2c7a7b;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e1e4e8;
    }
    
    /* Headers */
    h1, h2, h3 { 
        color: #0d2621; 
        font-weight: 700; 
        letter-spacing: -0.02em;
    }
    
    /* Buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #2c7a7b 0%, #285e61 100%);
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background: linear-gradient(135deg, #319795 0%, #2c7a7b 100%);
        transform: scale(1.02);
        box-shadow: 0 4px 6px rgba(0,0,0,0.15);
    }
    
    /* Input Fields */
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: white;
        border-radius: 8px;
        color: #4a5568;
        border: 1px solid #e2e8f0;
        padding: 0 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #e6fffa !important;
        color: #234e52 !important;
        border-color: #38b2ac !important;
        font-weight: 600;
    }
    
    /* Chat Bubbles */
    .stChatMessage {
        background-color: white;
        border: 1px solid #edf2f7;
        border-radius: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Initialization & Data
# -----------------------------------------------------------------------------

@st.cache_resource
def load_graph_app():
    return build_esg_graph()

graph_app = load_graph_app()

@st.cache_data
def load_data():
    parsed = {}
    metrics = {}
    if PARSED.exists():
        try:
            parsed = json.loads(PARSED.read_text(encoding='utf-8'))
        except: pass
    if METRICS.exists():
        try:
            metrics = json.loads(METRICS.read_text(encoding='utf-8'))
        except: pass
    return parsed, metrics

parsed, metrics = load_data()
companies = list(parsed.keys()) if isinstance(parsed, dict) else []

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def format_big_number(num):
    if num is None: return "N/A"
    try:
        n = float(num)
    except:
        return str(num)
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.0f}k"
    return f"{n:,.0f}"

# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
        <div style="padding: 1rem 0; background: linear-gradient(90deg, #1a3c34 0%, #2c7a7b 100%); border-radius: 8px; margin-bottom: 20px; text-align: center;">
            <h1 style="color: white; font-size: 24px; margin: 0;">🌿 ESG Analyser</h1>
        </div>
    """, unsafe_allow_html=True)
    
    selected_company = st.selectbox("Select Company Report", options=companies, index=0 if companies else None)
    
    st.markdown("### ⚙️ Settings")
    st.caption("Using Local LLM (Ollama) & Nomic Embeddings")
    

    
    st.markdown("---")
    st.info("Powered by LangGraph & Local LLMs")

if not selected_company:
    st.warning("No reports found. (Check parsed_structured.json)")
    st.stop()

# -----------------------------------------------------------------------------
# Main Content
# -----------------------------------------------------------------------------

st.title(f"📊 Report Analysis: {selected_company.split('_')[0]}")

# Metric Cards
comp_metrics = metrics.get(selected_company, {})
if comp_metrics:
    cols = st.columns(4)
    display_keys = {
        'carbon_emissions': 'Emissions (CO2e)', 
        'energy_usage': 'Energy Usage', 
        'renewable_energy_percent': 'Renewable %', 
        'waste_generated': 'Waste'
    }
    for idx, (key, label) in enumerate(display_keys.items()):
        val = comp_metrics.get(key)
        with cols[idx]:
             st.metric(label, format_big_number(val) if key != 'renewable_energy_percent' else f"{val}%" if val else "N/A")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["🤖 AI Assistant", "🔍 Data Deep Dive", "⚔️ Comparison"])

# --- TAB 1: AI ASSISTANT (Chat with Graph) ---
with tab1:
    st.header("Ask the Agent")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Quick Prompts
    st.caption("Quick Prompts:")
    qp_cols = st.columns(4)
    quick_prompt = None
    if qp_cols[0].button("📝 Summarize"): quick_prompt = "Summarize the executive letter and key goals."
    if qp_cols[1].button("📉 Emissions"): quick_prompt = "What are the scope 1, 2, and 3 emissions?"
    if qp_cols[2].button("🎯 Future Goals"): quick_prompt = "list the 2030 environmental targets."
    if qp_cols[3].button("💧 Water Usage"): quick_prompt = "What is the total water withdrawal?"

    # Handle Input (Chat Input OR Quick Prompt)
    topic = st.chat_input("Ask about the report...")
    if quick_prompt: topic = quick_prompt # Priority to quick prompt if clicked

    if topic:
        st.session_state.messages.append({"role": "user", "content": topic})
        with st.chat_message("user"):
            st.markdown(topic)

        with st.chat_message("assistant"):
            with st.spinner("Agent working..."):
                try:
                    inputs = {"question": topic, "company": selected_company}
                    
                    # Run the graph (Synchronous)
                    result = graph_app.invoke(inputs)
                    final_resp = result.get("final_answer", "I couldn't generate an answer.")
                    
                    if final_resp.startswith("DISPLAY_REPORT_FLAG"):
                        # Clean UI for large report text
                        clean_text = final_resp.replace("DISPLAY_REPORT_FLAG\n\n", "")
                        st.markdown("### 📄 Report Content Preview")
                        with st.expander("View Extracted Text", expanded=True):
                            st.text_area("Content", value=clean_text, height=400)
                        st.session_state.messages.append({"role": "assistant", "content": "I've displayed the requested report text above."})
                    else:
                        st.markdown(final_resp)
                        st.session_state.messages.append({"role": "assistant", "content": final_resp})
                        
                    # DATA & ACCURACY: Context Inspector
                    # Show sources if available
                    sources = result.get("documents", [])
                    if sources:
                        with st.expander("📚 View Source Context"):
                            import re
                            for i, s in enumerate(sources):
                                    # Better Context Label
                                    header_match = re.search(r'#{1,3}\s+(.+?)\n', s)
                                    clean_header = header_match.group(1).strip()[:50] if header_match else "General Context"
                                    
                                    source_label = f"📄 **Source {i+1}**: _{clean_header}..._"
                                    st.caption(source_label)
                                    
                                    # Check for images in the text
                                    img_matches = re.findall(r'!\[.*?\]\((.*?)\)', s)
                                    if img_matches:
                                        for img_path in img_matches:
                                            if os.path.exists(img_path):
                                                st.image(img_path, caption=f"Ref: Figure from '{clean_header}'", width=500)
                                    
                                    # Show preview text
                                    clean_text = re.sub(r'\[Source:.*?\]', '', s).strip()
                                    # Remove image links from text preview to avoid clutter
                                    clean_text = re.sub(r'!\[.*?\]\(.*?\)', '[Figure Embedded Above]', clean_text)
                                    st.text(clean_text[:400] + "..." if len(clean_text)>400 else clean_text)
                    
                except Exception as e:
                    st.error(f"Graph Error: {e}")

# --- TAB 2: DEEP DIVE (Raw Data) ---
with tab2:
    st.header(f"🔍 Deep Dive: {selected_company}")
    
    data = parsed.get(selected_company, {})
    tables_raw = data.get("tables", [])
    text_content = data.get("text", "")

    # Segregated View using Inner Tabs
    d_tab1, d_tab2 = st.tabs(["Full Report Text", "Extracted Tables"])

    with d_tab1:
        st.markdown("**Raw PDF Text Extraction**")
        if text_content:
            # Format text for better readability (Markdown paragraphs)
            formatted_text = text_content[:25000].replace("\n", "\n\n")
            if len(text_content) > 25000:
                formatted_text += "\n\n... [Truncated for Performance]"
            
            with st.container(height=600):
                st.markdown(formatted_text)
        else:
            st.warning("No text extracted.")

    with d_tab2:
        
        if tables_raw:
            st.info(f"Found {len(tables_raw)} structured tables.")
            
            # List tables clearly
            for i, tbl in enumerate(tables_raw):
                rows = tbl.get('rows', []) if isinstance(tbl, dict) else tbl
                if not rows: continue
                
                df = pd.DataFrame(rows)
                
                # Check for empty columns and drop them for display
                df = df.dropna(axis=1, how='all')
                
                # Renamed expander label to "Table X"
                with st.expander(f"Table {i+1}", expanded=(i==0)):
                    st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("No structured tables detected in this report.")

# --- TAB 3: COMPARISON ---
with tab3:
    st.header("Competitive Analysis")
    
    if len(metrics) > 1:
        st.caption("Industry Key Metrics Overview")
        
        # Prepare Data for all charts
        rows_emissions = []
        rows_energy = []
        rows_waste = []
        
        # Aggregate ALL data for export
        all_export_rows = []
        
        for c, m in metrics.items():
            name = c.split('_')[0]
            row_full = {'Company': name, **m}
            all_export_rows.append(row_full)
            
            if m.get('carbon_emissions'):
                rows_emissions.append({'Company': name, 'Emissions (CO2e)': m['carbon_emissions']})
            if m.get('energy_usage'):
                rows_energy.append({'Company': name, 'Energy Input (MWh)': m['energy_usage']})
            if m.get('waste_generated'):
                rows_waste.append({'Company': name, 'Waste (Tons)': m['waste_generated']})



        # Columns for 3 charts
        g_col1, g_col2, g_col3 = st.columns(3)
        
        # Define a consistent chart helper
        def make_chart(data, y_field, color_scheme='tealblues'):
            base = alt.Chart(pd.DataFrame(data)).encode(
                x=alt.X('Company', axis=alt.Axis(labels=False, title=None)),
                y=alt.Y(y_field, axis=alt.Axis(grid=True, title=None)),
                color=alt.Color('Company', scale=alt.Scale(scheme=color_scheme), legend=alt.Legend(orient='bottom')),
                tooltip=['Company', y_field]
            )
            
            bars = base.mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
            
            # Add text labels on top of bars
            text = base.mark_text(dy=-10, color='black').encode(text=alt.Text(y_field, format=",.2f" if 'Percent' not in y_field else ".1f"))

            return (bars + text).properties(height=300)

        with g_col1:
            st.subheader("CO2 Emissions")
            if rows_emissions:
                st.altair_chart(make_chart(rows_emissions, 'Emissions (CO2e)'), use_container_width=True)
            else:
                st.info("No Data")

        with g_col2:
            st.subheader("Energy Usage")
            if rows_energy:
                st.altair_chart(make_chart(rows_energy, 'Energy Input (MWh)'), use_container_width=True)
            else:
                st.info("No Data")
                
        with g_col3:
            st.subheader("Total Waste")
            if rows_waste:
                st.altair_chart(make_chart(rows_waste, 'Waste (Tons)'), use_container_width=True)
            else:
                st.info("No Data")

        st.markdown("---")
        
        # Display Comparison Table
        st.subheader("📋 Detailed Metrics Table")
        if all_export_rows:
            comp_df = pd.DataFrame(all_export_rows)
            # Reorder columns for better readability if they exist
            preferred_cols = ['Company', 'carbon_emissions', 'energy_usage', 'waste_generated', 'renewable_energy_percent', 'water_usage']
            cols_to_show = [c for c in preferred_cols if c in comp_df.columns] + [c for c in comp_df.columns if c not in preferred_cols]
            
            # Formatting for display
            display_df = comp_df[cols_to_show].copy()
            
            # Rename for display
            display_df.rename(columns={
                'carbon_emissions': 'Emissions (CO2e)',
                'energy_usage': 'Energy Usage (MWh)',
                'waste_generated': 'Waste (Tons)',
                'renewable_energy_percent': 'Renewable %',
                'water_usage': 'Water Withdrawal'
            }, inplace=True)
            
            # Simple number formatting
            for col in display_df.columns:
                if col != 'Company':
                    display_df[col] = display_df[col].apply(lambda x: format_big_number(x) if isinstance(x, (int, float)) else x)
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
                
        # EXPORT FEATURE
        st.markdown("### 📥 Export Data")
        if all_export_rows:
            export_df = pd.DataFrame(all_export_rows)
            csv = export_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Metrics CSV",
                csv,
                "esg_comparison_metrics.csv",
                "text/csv",
                key='download-csv'
            )
            
            # --- PDF REPORT EXPORT ---
            if 'last_comparison' in st.session_state:
                st.download_button(
                    "📄 Download Executive PDF Report",
                    data=create_pdf(all_export_rows, st.session_state['last_comparison']),
                    file_name="ESG_Executive_Report_2025.pdf",
                    mime="application/pdf",
                    key='download-pdf'
                )
            elif all_export_rows:
                 st.caption("ℹ️ *Run a comparison query below to unlock the full PDF report with AI analysis.*")

    st.divider()
    st.divider()
    st.subheader("Ask the Agent")
    
    # Suggestion Buttons
    st.caption("Quick Comparison Ideas:")
    sq_cols = st.columns(4)
    suggested_q = None
    
    if sq_cols[0].button("🔰 Net Zero & Goals"): 
        suggested_q = "Compare the Net Zero target years and specific 2030 interim reduction goals for each company."
    if sq_cols[1].button("👥 Diversity Metrics"): 
        suggested_q = "Compare diversity and inclusion metrics, specifically regarding women in leadership roles and overall workforce demographics."
    if sq_cols[2].button("🌍 Scope 3 Strategy"): 
        suggested_q = "Analyze how each company is addressing Scope 3 (supply chain) emissions and describe their supplier engagement programs."
    if sq_cols[3].button("🌊 Water Positivity"): 
        suggested_q = "Compare the 'Water Positive' commitments, deadlines, and current replenishment progress for each company."

    # Input Field (defaults to suggestion if clicked)
    # We use key='comp_input' to manage state if needed, but simple variable passing works for immediate trigger
    comp_prompt = st.text_input("Comparison Question:", value=suggested_q if suggested_q else "", placeholder="Compare water usage between companies...")
    
    # Trigger if button 'Compare' is clicked OR if a suggestion was just clicked
    if st.button("Compare") or suggested_q:
        if not comp_prompt and not suggested_q:
            st.warning("Please enter a question.")
        else:
            query_to_run = suggested_q if suggested_q else comp_prompt
            with st.spinner("Analyzing..."):
                try:
                    inputs = {"question": query_to_run, "company": "ALL"} 
                    result = graph_app.invoke(inputs)
                    final_ans = result.get("final_answer")
                    st.markdown(final_ans)
                    # Save for PDF export
                    st.session_state['last_comparison'] = final_ans
                except Exception as e:
                    st.error(f"Error: {e}")
