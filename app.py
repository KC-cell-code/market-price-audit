import os
import tempfile
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from fpdf import FPDF

# ==============================================================================
# 1. STREAMLIT PAGE CONFIG & SESSION STATE
# ==============================================================================
st.set_page_config(
    page_title="Market Price Audit Tool", page_icon="📊", layout="wide"
)

# Initialize persistent session state for data storage across reruns
if "audit_df" not in st.session_state:
  st.session_state.audit_df = audit_df


# ==============================================================================
# 2. PDF GENERATION HELPER FUNCTION
# ==============================================================================
def generate_pdf_bytes(audit_df):
  if audit_df.empty:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "No audit data available for PDF generation.", ln=True)
    return bytes(pdf.output())

  comp_market_avg = audit_df["Comp Avg (£)"].mean()
  client_market_avg = audit_df["Client Price (£)"].mean()
  overpriced_count = len(audit_df[audit_df["Difference (£)"] > 0])
  underpriced_count = len(audit_df[audit_df["Difference (£)"] < 0])
  price_diff = client_market_avg - comp_market_avg

  comparison = audit_df.head(8)

  # Generate Chart Image
  temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
  temp_img_path = temp_img.name
  temp_img.close()

  fig, ax = plt.subplots(figsize=(8, 3))
  x = range(len(comparison))
  width = 0.35
  ax.bar(
      [i - width / 2 for i in x],
      comparison["Client Price (£)"],
      width,
      label="Our Client",
      color="#1E3A8A",
  )
  ax.bar(
      [i + width / 2 for i in x],
      comparison["Comp Avg (£)"],
      width,
      label="Market Benchmark",
      color="#64748B",
  )
  ax.set_xticks(x)
  short_labels = [
      str(p)[:12] + "..." if len(str(p)) > 12 else str(p)
      for p in comparison["Product"]
  ]
  ax.set_xticklabels(short_labels, fontsize=8, rotation=15)
  ax.spines["top"].set_visible(False)
  ax.spines["right"].set_visible(False)
  ax.legend()
  plt.tight_layout()
  plt.savefig(temp_img_path, dpi=200)
  plt.close(fig)

  # Build FPDF Document
  pdf = FPDF()
  pdf.add_page()

  pdf.set_font("Arial", "B", 16)
  pdf.cell(
      0,
      10,
      txt="Market Intelligence & Competitive Audit",
      ln=True,
      align="C",
  )
  pdf.ln(3)

  # Dynamic Insights
  pdf.set_font("Arial", "B", 11)
  pdf.set_text_color(30, 58, 138)
  pdf.cell(0, 6, txt="Automated Market Insights:", ln=True)

  pdf.set_font("Arial", "", 9)
  pdf.set_text_color(51, 65, 85)

  pos_direction = "HIGHER" if price_diff > 0 else "LOWER"
  insight_pos = (
      f"* Positioning: Client products average \xa3{abs(price_diff):.2f}"
      f" {pos_direction} than the benchmark."
  )
  pdf.set_x(pdf.l_margin)
  pdf.multi_cell(0, 5, txt=str(insight_pos))

  if overpriced_count > 0:
    insight_risk = (
        f"* Key Risk: {overpriced_count} product(s) sit above market"
        " average."
    )
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, txt=str(insight_risk))

  if underpriced_count > 0:
    insight_opp = (
        f"* Opportunity: {underpriced_count} product(s) sit below benchmark"
        " (margin potential)."
    )
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, txt=str(insight_opp))

  pdf.ln(4)
  pdf.image(temp_img_path, x=15, w=180)
  pdf.ln(4)

  # Audit Table Header
  pdf.set_font("Arial", "B", 9)
  pdf.set_fill_color(30, 58, 138)
  pdf.set_text_color(255, 255, 255)
  w_item, w_client, w_comp, w_diff = 75, 35, 40, 40

  pdf.cell(w_item, 7, "Product Title", border=1, align="C", fill=True)
  pdf.cell(w_client, 7, "Client (\xa3)", border=1, align="C", fill=True)
  pdf.cell(w_comp, 7, "Benchmark (\xa3)", border=1, align="C", fill=True)
  pdf.cell(w_diff, 7, "Variance (\xa3)", border=1, align="C", fill=True)
  pdf.ln()

  # Color-Coded Table Rows
  pdf.set_font("Arial", "", 8)
  pdf.set_text_color(0, 0, 0)

  for _, row in audit_df.iterrows():
    diff_val = row["Difference (£)"]
    diff_str = f"+{diff_val:.2f}" if diff_val > 0 else f"{diff_val:.2f}"
    clean_title = (
        str(row["Product"]).encode("latin-1", "replace").decode("latin-1")[:38]
    )

    if diff_val > 0:
      pdf.set_fill_color(254, 226, 226)
    elif diff_val < 0:
      pdf.set_fill_color(220, 252, 231)
    else:
      pdf.set_fill_color(255, 255, 255)

    pdf.cell(w_item, 6, clean_title, border=1, align="L", fill=True)
    pdf.cell(
        w_client,
        6,
        f"{row['Client Price (£)']:.2f}",
        border=1,
        align="C",
        fill=True,
    )
    pdf.cell(
        w_comp, 6, f"{row['Comp Avg (£)']:.2f}", border=1, align="C", fill=True
    )
    pdf.cell(w_diff, 6, diff_str, border=1, align="C", fill=True)
    pdf.ln()

  if os.path.exists(temp_img_path):
    os.remove(temp_img_path)

    return bytes(pdf.output())



# ==============================================================================
# 3. UI LAYOUT & DATA INPUT
# ==============================================================================
st.title("📊 Market Price Audit Tool")
st.write(
    "Upload pricing data or use sample data to generate competitive market"
    " audits."
)

st.sidebar.header("Data Source")
data_source = st.sidebar.radio(
    "Select Input Method:", ("Upload CSV/Excel", "Use Sample Data")
)

raw_df = None

if data_source == "Upload CSV/Excel":
  uploaded_file = st.file_uploader(
      "Upload pricing spreadsheet", type=["csv", "xlsx"]
  )
  if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
      raw_df = pd.read_csv(uploaded_file)
    else:
      raw_df = pd.read_excel(uploaded_file)
else:
  # Built-in fallback sample data
  sample_data = {
      "Product Title": [
          "Wireless Ergonomic Mouse",
          "Mechanical RGB Keyboard",
          "27-inch 1440p Gaming Monitor",
          "USB-C Docking Station",
          "Noise-Canceling Headphones",
      ],
      "Client Price": [29.99, 85.00, 240.00, 65.00, 110.00],
      "Benchmark Price": [24.50, 89.99, 219.00, 75.00, 95.00],
  }
  raw_df = pd.DataFrame(sample_data)

# ==============================================================================
# 4. COLUMN MAPPING & AUDIT CREATION
# ==============================================================================
if raw_df is not None:
  st.subheader("Data Mapping & Processing")

  col1, col2, col3 = st.columns(3)
  cols = list(raw_df.columns)

  with col1:
    prod_col = st.selectbox(
        "Product Name Column", cols, index=0 if len(cols) > 0 else 0
    )
  with col2:
    client_col = st.selectbox(
        "Client Price Column", cols, index=1 if len(cols) > 1 else 0
    )
  with col3:
    comp_col = st.selectbox(
        "Benchmark Price Column", cols, index=2 if len(cols) > 2 else 0
    )

  if st.button("🚀 Run Market Audit", type="primary"):
    processed_df = pd.DataFrame()
    processed_df["Product"] = raw_df[prod_col].astype(str)

    # Force numeric type conversions to prevent blank/NaN data bugs
    processed_df["Client Price (£)"] = pd.to_numeric(
        raw_df[client_col], errors="coerce"
    ).fillna(0.0)
    processed_df["Comp Avg (£)"] = pd.to_numeric(
        raw_df[comp_col], errors="coerce"
    ).fillna(0.0)
    processed_df["Difference (£)"] = (
        processed_df["Client Price (£)"] - processed_df["Comp Avg (£)"]
    )

    # Save created audit_df into session state so it persists across reruns
    st.session_state.audit_df = processed_df
    st.success("Audit generated successfully!")

# ==============================================================================
# 5. RENDER RESULTS & EXPORT PDF
# ==============================================================================
if "audit_df" in st.session_state and not st.session_state.audit_df.empty:
  audit_df = st.session_state.audit_df

  st.markdown("---")
  st.subheader("Audit Results")

  m1, m2, m3, m4 = st.columns(4)
  avg_client = audit_df["Client Price (£)"].mean()
  avg_comp = audit_df["Comp Avg (£)"].mean()
  overpriced = len(audit_df[audit_df["Difference (£)"] > 0])
  underpriced = len(audit_df[audit_df["Difference (£)"] < 0])

  m1.metric("Avg Client Price", f"£{avg_client:.2f}")
  m2.metric("Avg Benchmark Price", f"£{avg_comp:.2f}")
  m3.metric("Overpriced Items", f"{overpriced}")
  m4.metric("Underpriced Items", f"{underpriced}")

  st.dataframe(
      audit_df.style.format({
          "Client Price (£)": "£{:.2f}",
          "Comp Avg (£)": "£{:.2f}",
          "Difference (£)": "£{:+.2f}",
      }),
      use_container_width=True,
  )

  pdf_bytes = generate_pdf_bytes(audit_df)

  st.sidebar.markdown("---")
  st.sidebar.subheader("Export Report")
  st.sidebar.download_button(
      label="📄 Download PDF Market Audit",
      data=pdf_bytes,
      file_name="market_audit_report.pdf",
      mime="application/pdf",
      use_container_width=True,
  )
else:
  st.info(
      "Select a data source, map your columns, and click **Run Market Audit**"
      " to view results."
  )