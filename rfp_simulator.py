# rfp_simulator.py
# Streamlit RFP Simulator - calculate/display results + export XLSX/PDF
# Run from terminal:   streamlit run rfp_simulator.py
#
# FIX: use st.form("rfp_form") instead of st.form("form") to avoid session_state key collision.

import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import datetime

st.set_page_config(page_title="RFP Simulator", layout="wide")

# ---------------------------
# Configuration / assumptions
# ---------------------------
CURRENCY = "$"
ANNUAL_COST_PER_FTE = 60000
IMPLEMENTATION_PCT = 0.20
SAVINGS_PCT = 0.30

TECH_LICENSE_COSTS = {
    "RPA": 5000,
    "VBA": 0,
    "Celonis": 10000,
    "Soroco": 8000,
    "Analytics": 7000,
    "AI": 12000
}

DEV_COSTS = {
    "RPA": 20000,
    "VBA": 1000,
    "Celonis": 30000,
    "Soroco": 25000,
    "Analytics": 15000,
    "AI": 40000
}

USER_LICENSE_PER_TECH = {
    "RPA": 100,
    "VBA": 0,
    "Celonis": 200,
    "Soroco": 150,
    "Analytics": 120,
    "AI": 250
}

ALL_TECHS = list(TECH_LICENSE_COSTS.keys())

# ---------------------------
# Helper Functions
# ---------------------------
def fmt_money(x):
    try:
        return f"{CURRENCY}{int(round(x)):,}"
    except:
        return f"{CURRENCY}0"

def per_solution_table(headcount, selected_techs):
    rows = []
    for tech in ALL_TECHS:
        license_cost = TECH_LICENSE_COSTS[tech] if tech in selected_techs else 0
        dev_cost = DEV_COSTS[tech] if tech in selected_techs else 0
        user_license_cost = USER_LICENSE_PER_TECH[tech] * headcount if tech in selected_techs else 0
        total_cost = license_cost + dev_cost + user_license_cost

        rows.append({
            "Solution": tech,
            "License Cost": license_cost,
            "Development Cost": dev_cost,
            "User License Cost": user_license_cost,
            "Total Cost": total_cost
        })

    totals = {
        "Solution": "Total Cost",
        "License Cost": sum(r["License Cost"] for r in rows),
        "Development Cost": sum(r["Development Cost"] for r in rows),
        "User License Cost": sum(r["User License Cost"] for r in rows),
        "Total Cost": sum(r["Total Cost"] for r in rows),
    }
    rows.append(totals)

    return pd.DataFrame(rows)

def calculate_costs(headcount, selected_techs):
    headcount_cost = headcount * ANNUAL_COST_PER_FTE
    implementation_cost = headcount_cost * IMPLEMENTATION_PCT
    annual_savings = headcount_cost * SAVINGS_PCT
    tech_cost = sum(TECH_LICENSE_COSTS.get(t, 0) for t in selected_techs)

    net_annual_cost = headcount_cost - annual_savings + tech_cost

    payback_years = None
    if annual_savings and annual_savings > 0:
        try:
            payback_years = implementation_cost / annual_savings
        except:
            payback_years = None

    return {
        "headcount_cost": headcount_cost,
        "implementation_cost": implementation_cost,
        "tech_cost": tech_cost,
        "annual_savings": annual_savings,
        "net_annual_cost": net_annual_cost,
        "payback_years": payback_years
    }

def to_excel_bytes(df_dict, run_meta):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for name, df in df_dict.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)

        meta_df = pd.DataFrame(list(run_meta.items()), columns=["Key", "Value"])
        meta_df.to_excel(writer, sheet_name="Meta", index=False)

        writer.save()

    return output.getvalue()

def to_pdf_bytes(run_meta, inputs_display, df_solutions, financial_summary):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "RFP Simulator Summary", ln=True)

    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"Run ID: {run_meta.get('RunID','')}", ln=True)
    pdf.cell(0, 6, f"Timestamp: {run_meta.get('Timestamp','')}", ln=True)
    pdf.ln(4)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, "Inputs", ln=True)

    pdf.set_font("Arial", size=10)
    for k, v in inputs_display.items():
        pdf.cell(0, 6, f"{k}: {v}", ln=True)

    pdf.ln(4)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, "Solution Cost Breakdown", ln=True)
    pdf.set_font("Arial", size=9)

    col_w = [45, 30, 35, 35, 35]
    headers = ["Solution", "License", "Dev", "User Lic", "Total"]

    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 6, h, border=1)
    pdf.ln()

    for _, row in df_solutions.iterrows():
        pdf.cell(col_w[0], 6, str(row.get("Solution","")), border=1)
        pdf.cell(col_w[1], 6, fmt_money(row.get("License Cost",0)), border=1)
        pdf.cell(col_w[2], 6, fmt_money(row.get("Development Cost",0)), border=1)
        pdf.cell(col_w[3], 6, fmt_money(row.get("User License Cost",0)), border=1)
        pdf.cell(col_w[4], 6, fmt_money(row.get("Total Cost",0)), border=1)
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, "Financial Summary", ln=True)
    pdf.set_font("Arial", size=10)

    for k, v in financial_summary.items():
        pdf.cell(0, 6, f"{k}: {v}", ln=True)

    return pdf.output(dest="S").encode("latin1")

# ---------------------------
# UI - Input Form
# ---------------------------
st.title("RFP Simulator")
st.write("Enter details and click **Calculate** to view the cost breakdown and export results.")

# session state keys
if "form" not in st.session_state:
    st.session_state.form = {
        "headcount": "",
        "region": "",
        "hc_category": "",
        "process_type": "",
        "transform_scale": "",
        "techs": []
    }

# NOTE: form widget key renamed to "rfp_form" to avoid collision with session_state.form
with st.form("rfp_form"):
    col1, col2 = st.columns(2)

    with col1:
        headcount = st.text_input("Headcount", st.session_state.form["headcount"])
        region = st.selectbox("Region", ["", "North America", "EMEA", "APAC", "LATAM"], index=0 if st.session_state.form["region"]=="" else None)
        hc_category = st.selectbox("HC Category", ["", "Ops", "Finance", "IT", "HR"], index=0 if st.session_state.form["hc_category"]=="" else None)

    with col2:
        process_type = st.selectbox("Process Type", ["", "Claims", "Billing", "Enrollment", "Customer Service"], index=0 if st.session_state.form["process_type"]=="" else None)
        transform_scale = st.selectbox("Transformation Scale", ["", "Small", "Medium", "Large"], index=0 if st.session_state.form["transform_scale"]=="" else None)

        st.markdown("**Technologies**")
        techs = []
        tcols = st.columns(3)
        idx = 0
        for t in ALL_TECHS:
            if tcols[idx % 3].checkbox(t, value=(t in st.session_state.form["techs"])):
                techs.append(t)
            idx += 1

    c1, c2, c3 = st.columns(3)
    calculate = c1.form_submit_button("Calculate")
    sample = c2.form_submit_button("Sample Data")
    reset = c3.form_submit_button("Reset")

# Reset
if reset:
    st.session_state.form = {k: "" if k != "techs" else [] for k in st.session_state.form}
    st.experimental_rerun()

# Sample
if sample:
    st.session_state.form = {
        "headcount": "25",
        "region": "North America",
        "hc_category": "Ops",
        "process_type": "Claims",
        "transform_scale": "Large",
        "techs": ["RPA", "AI"]
    }
    st.experimental_rerun()

# ---------------------------
# Calculate
# ---------------------------
if calculate:
    # persist current inputs
    st.session_state.form.update({
        "headcount": headcount,
        "region": region,
        "hc_category": hc_category,
        "process_type": process_type,
        "transform_scale": transform_scale,
        "techs": techs
    })

    # Validation
    errors = []

    try:
        hc_val = int(float(str(headcount).strip()))
        if hc_val <= 0:
            errors.append("Headcount must be > 0.")
    except:
        errors.append("Headcount must be an integer.")

    if not region or not hc_category or not process_type or not transform_scale:
        errors.append("All dropdowns are mandatory.")

    if errors:
        st.error("Fix these errors:")
        for e in errors:
            st.write("- " + e)
        st.stop()

    # Calculations
    results = calculate_costs(hc_val, techs)
    df_solutions = per_solution_table(hc_val, techs)

    st.subheader("Solution Cost Breakdown")
    df_display = df_solutions.copy()
    for col in ["License Cost", "Development Cost", "User License Cost", "Total Cost"]:
        df_display[col] = df_display[col].apply(fmt_money)
    st.table(df_display.set_index("Solution"))

    st.markdown("---")
    st.subheader("Financial Overview")

    c1, c2, c3 = st.columns(3)
    c1.metric("Annual Labor Cost", fmt_money(results["headcount_cost"]))
    c2.metric("Estimated Annual Savings", fmt_money(-results["annual_savings"]))
    c3.metric("Annual Tooling (selected)", fmt_money(results["tech_cost"]))

    st.write("**Implementation (one-time):**", fmt_money(results["implementation_cost"]))
    st.write("**Net Annual Cost:**", fmt_money(results["net_annual_cost"]))
    if results["payback_years"]:
        st.write("**Payback (years):**", round(results["payback_years"], 2))

    # Export section
    run_meta = {
        "RunID": "RUN-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    inputs_display = {
        "Headcount": hc_val,
        "Region": region,
        "HC Category": hc_category,
        "Process Type": process_type,
        "Transformation Scale": transform_scale,
        "Technologies": ", ".join(techs) if techs else "None"
    }

    financial_summary = {
        "Annual Labor": fmt_money(results["headcount_cost"]),
        "Annual Savings": fmt_money(-results["annual_savings"]),
        "Annual Tooling": fmt_money(results["tech_cost"]),
        "Implementation": fmt_money(results["implementation_cost"]),
        "Net Annual Cost": fmt_money(results["net_annual_cost"])
    }

    df_excel = {
        "Solutions": df_solutions,
        "Inputs": pd.DataFrame(list(inputs_display.items()), columns=["Field", "Value"])
    }

    excel_bytes = to_excel_bytes(df_excel, run_meta)
    st.download_button(
        "📥 Download Excel (.xlsx)",
        data=excel_bytes,
        file_name=f"RFP_Results_{run_meta['RunID']}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    pdf_bytes = to_pdf_bytes(run_meta, inputs_display, df_solutions, financial_summary)
    st.download_button(
        "📄 Download PDF Summary",
        data=pdf_bytes,
        file_name=f"RFP_Summary_{run_meta['RunID']}.pdf",
        mime="application/pdf"
    )
