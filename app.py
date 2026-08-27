#streamlit run app.py
import os
import re
import tempfile
import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from fpdf import FPDF

# 1. PAGE SETUP
st.set_page_config(
    page_title="Market Price Audit Dashboard",
    page_icon="📊",
    layout="wide",
)

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import smtplib


def send_price_alert(overpriced_df, recipient_email):
  """Sends an HTML email alert when competitor prices undercut client prices."""
  if overpriced_df.empty:
    st.info("No price drops detected. Skipping email alert.")
    return False

  # Replace with your actual sender Gmail and 16-char App Password
  sender_email = os.environ.get(
      "ALERT_EMAIL_USER", "krccjc8@gmail.com"
  )
  sender_password = os.environ.get("ALERT_EMAIL_PASS", "bhhsqantckaklpvz")

  msg = MIMEMultipart("alternative")
  msg["Subject"] = "🚨 Market Alert: Competitors Undercutting Client Prices"
  msg["From"] = sender_email
  msg["To"] = recipient_email

  table_rows = ""
  for _, row in overpriced_df.iterrows():
    diff_val = row.get("Difference (£)", row.get("Diff (£)", 0.0))
    table_rows += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{row['Product']}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">£{row['Price (£)']:.2f}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center; color: #dc2626;">£{row['Comp Avg (£)']:.2f}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: bold;">+£{diff_val:.2f}</td>
        </tr>
        """

  html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #1E3A8A;">Competitor Price Drop Detected</h2>
        <p>The following client items are currently <b>more expensive</b> than the market average:</p>
        <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
            <thead>
                <tr style="background-color: #1E3A8A; color: white;">
                    <th style="padding: 8px; text-align: left;">Product</th>
                    <th style="padding: 8px;">Client Price</th>
                    <th style="padding: 8px;">Market Avg</th>
                    <th style="padding: 8px;">Client Premium</th>
                </tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
    </body>
    </html>
    """
  msg.attach(MIMEText(html_content, "html"))

  try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
      server.login(sender_email, sender_password)
      server.sendmail(sender_email, recipient_email, msg.as_string())
    return True
  except Exception as e:
    st.error(f"Failed to send email: {e}")
    return False

# 2. PDF GENERATION HELPER FUNCTION
def generate_pdf_bytes(df_to_report):
  client_name = "Our Client"
  client_data = df_to_report[df_to_report["Shop"] == client_name]
  comp_data = df_to_report[df_to_report["Shop"] != client_name]

  comp_market_avg = comp_data["Price (£)"].mean() if not comp_data.empty else 0
  client_market_avg = (
      client_data["Price (£)"].mean() if not client_data.empty else 0
  )

  comp_avg_per_item = (
      comp_data.groupby("Product")["Price (£)"]
      .mean()
      .reset_index()
      .rename(columns={"Price (£)": "Comp Avg (£)"})
  )

  comparison = pd.merge(
      client_data, comp_avg_per_item, on="Product", how="inner"
  )
  if comparison.empty:
    comparison = client_data.copy()
    comparison["Comp Avg (£)"] = comp_market_avg

  comparison["Difference (£)"] = (
      comparison["Price (£)"] - comparison["Comp Avg (£)"]
  ).round(2)

  overpriced_count = len(comparison[comparison["Difference (£)"] > 0])
  underpriced_count = len(comparison[comparison["Difference (£)"] < 0])
  price_diff = client_market_avg - comp_market_avg

  comparison = comparison.head(8)

  # 1. Create temporary chart image file
  temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
  temp_img_path = temp_img.name
  temp_img.close()

  fig, ax = plt.subplots(figsize=(8, 3))
  x = range(len(comparison))
  width = 0.35
  ax.bar(
      [i - width / 2 for i in x],
      comparison["Price (£)"],
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
      p[:12] + "..." if len(p) > 12 else p for p in comparison["Product"]
  ]
  ax.set_xticklabels(short_labels, fontsize=8, rotation=15)
  ax.spines["top"].set_visible(False)
  ax.spines["right"].set_visible(False)
  ax.legend()
  plt.tight_layout()

  plt.savefig(temp_img_path, dpi=200)
  plt.close(fig)

  # 2. Build PDF Document
  pdf = FPDF()
  pdf.add_page()

  # Title Header
  pdf.set_font("Arial", "B", 16)
  pdf.cell(
      0,
      10,
      txt="Market Intelligence & Competitive Audit",
      ln=True,
      align="C",
  )
  pdf.ln(3)

  # Dynamic Insights Block
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
  pdf.multi_cell(0, 5, text=str(insight_pos))

  if overpriced_count > 0:
      insight_risk = (
          f"* Key Risk: {overpriced_count} product(s) sit above market average."
      )
      pdf.ln(5)
      pdf.set_x(pdf.l_margin)
      pdf.multi_cell(0, 5, text=str(insight_risk))

  if underpriced_count > 0:
      insight_opp = (
          f"* Opportunity: {underpriced_count} product(s) sit below benchmark"
          " (margin potential)."
      )
      pdf.ln(5)  # Move down to a new line
      pdf.set_x(pdf.l_margin)  # Reset X position back to left margin
      pdf.multi_cell(0, 5, text=str(insight_opp))  # Render text using fpdf2 syntax

  pdf.ln(4)

  # Embed Chart
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

  # Audit Table Rows
  pdf.set_font("Arial", "", 8)
  pdf.set_text_color(51, 65, 85)
  for idx, row in comparison.iterrows():
    diff_val = row["Difference (£)"]
    diff_str = f"+{diff_val:.2f}" if diff_val > 0 else f"{diff_val:.2f}"
    clean_title = (
        str(row["Product"]).encode("latin-1", "replace").decode("latin-1")[:38]
    )

    pdf.cell(w_item, 6, clean_title, border=1, align="L")
    pdf.cell(w_client, 6, f"{row['Price (£)']:.2f}", border=1, align="C")
    pdf.cell(w_comp, 6, f"{row['Comp Avg (£)']:.2f}", border=1, align="C")
    pdf.cell(w_diff, 6, diff_str, border=1, align="C")
    pdf.ln()

  # 3. Output PDF Bytes & Cleanup
  temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
  temp_pdf_path = temp_pdf.name
  temp_pdf.close()

  pdf.output(temp_pdf_path)

  with open(temp_pdf_path, "rb") as f:
    pdf_bytes = f.read()

  if os.path.exists(temp_img_path):
    os.remove(temp_img_path)
  if os.path.exists(temp_pdf_path):
    os.remove(temp_pdf_path)

  return pdf_bytes

# 3. LIVE SCRAPER FUNCTION (Cached for 1 hour)
@st.cache_data(ttl=3600)
def load_and_scrape_data():
  targets_df = pd.read_csv("targets.csv")
  scraped_dataframes = []

  headers = {"User-Agent": "Mozilla/5.0"}
  for _, row in targets_df.iterrows():
    try:
      response = requests.get(row["URL"], headers=headers, timeout=5)
      soup = BeautifulSoup(response.text, "html.parser")
      items = []
      for product in soup.find_all("article", class_="product_pod"):
        title = product.h3.a["title"].strip()
        price_text = product.find("p", class_="price_color").text
        price = float(re.sub(r"[^\d.]", "", price_text))
        items.append(
            {"Shop": row["Shop"], "Product": title, "Price (£)": price}
        )
      scraped_dataframes.append(pd.DataFrame(items))
    except Exception as e:
      st.error(f"Could not scrape {row['Shop']}: {e}")

  return pd.concat(scraped_dataframes, ignore_index=True)


with st.spinner("Scraping live target sites..."):
  df = load_and_scrape_data()


# ==============================================================================
# 4. SIDEBAR CONTROLS (EVERYTHING IN THE LEFT PANEL LIVES HERE)
# ==============================================================================
st.sidebar.header("Filter Options")

# Store Multiselect
all_shops = list(df["Shop"].unique())
selected_shops = st.sidebar.multiselect(
    "Select Stores to Compare", options=all_shops, default=all_shops
)

# Price Range Slider
min_p = float(df["Price (£)"].min())
max_p = float(df["Price (£)"].max())
price_range = st.sidebar.slider(
    "Filter by Price (£)",
    min_value=min_p,
    max_value=max_p,
    value=(min_p, max_p),
)

# Apply Filters to Master Data
filtered_df = df[
    (df["Shop"].isin(selected_shops))
    & (df["Price (£)"] >= price_range[0])
    & (df["Price (£)"] <= price_range[1])
]

# Export Section inside Sidebar
st.sidebar.divider()
st.sidebar.subheader("Export Options")

pdf_data = generate_pdf_bytes(filtered_df)

st.sidebar.download_button(
    label="📄 Download PDF Market Audit",
    data=pdf_data,
    file_name="Market_Intelligence_Report.pdf",
    mime="application/pdf",
    use_container_width=True,
)


# ==============================================================================
# UPGRADED STREAMLIT SIDEBAR & FILTERS
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.subheader("Advanced Filters")

# 1. Category Filter (Assuming you have a 'Category' column, otherwise skips safely)
if "Category" in df.columns:
    categories = st.sidebar.multiselect(
        "Select Categories", options=df["Category"].unique(), default=df["Category"].unique()
    )
    filtered_df = filtered_df[filtered_df["Category"].isin(categories)]

# ==============================================================================
# 1. CALCULATIONS & DATA PREPARATION
# ==============================================================================
# Detect competitor column dynamically
possible_comp_cols = [
    "Comp Avg (£)",
    "Market Avg (£)",
    "Competitor Price (£)",
    "Benchmark (£)",
    "Market Price (£)",
]
comp_col = next(
    (col for col in possible_comp_cols if col in filtered_df.columns), None
)

if comp_col and "Price (£)" in filtered_df.columns:
  # Recalculate Difference (£) to ensure non-zero values
  filtered_df["Difference (£)"] = filtered_df["Price (£)"] - filtered_df[comp_col]

  # Calculate Recommended Price rounded to 2 decimal places
  target_margin = st.sidebar.slider(
      "Target Profit Margin (%)", min_value=5, max_value=50, value=15
  )
  filtered_df["Recommended Price (£)"] = (
      filtered_df[comp_col] * (1 + (target_margin / 100))
  ).round(2)
else:
  target_margin = 15

# Calculate Key Figures
total_audited = len(filtered_df)
avg_client_price = (
    filtered_df["Price (£)"].mean()
    if "Price (£)" in filtered_df.columns
    else 0.0
)
avg_market_price = (
    filtered_df[comp_col].mean() if comp_col else 0.0
)

overpriced_df = (
    filtered_df[filtered_df["Difference (£)"] > 0]
    if "Difference (£)" in filtered_df.columns
    else pd.DataFrame()
)
underpriced_df = (
    filtered_df[filtered_df["Difference (£)"] < 0]
    if "Difference (£)" in filtered_df.columns
    else pd.DataFrame()
)

overpriced_count = len(overpriced_df)
underpriced_count = len(underpriced_df)
avg_diff = (
    filtered_df["Difference (£)"].mean()
    if "Difference (£)" in filtered_df.columns
    else 0.0
)

# ==============================================================================
# 2. HEADER & ALL 6 METRIC CARDS
# ==============================================================================
st.title("📊 Market Intelligence & Audit Dashboard")

st.subheader("Overview Metrics")
# Row 1: Original 3 Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Total Products Audited", total_audited)
col2.metric("Avg Client Price", f"£{avg_client_price:.2f}")
col3.metric("Avg Market Price", f"£{avg_market_price:.2f}")

# Row 2: Additional Strategy KPIs
col4, col5, col6 = st.columns(3)
col4.metric(
    "Overpriced Items (Risk)", overpriced_count, delta=f"{overpriced_count} items", delta_color="inverse"
)
col5.metric(
    "Underpriced Items (Opportunity)", underpriced_count, delta=f"{underpriced_count} items"
)
col6.metric(
    "Avg Price Difference",
    f"£{abs(avg_diff):.2f}",
    delta=f"{'Above' if avg_diff > 0 else 'Below'} Market",
    delta_color="inverse",
)

st.markdown("---")

# ==============================================================================
# 3. RESTORED DYNAMIC EXECUTIVE INSIGHTS
# ==============================================================================
st.subheader("💡 Automated Insights")
pos_direction = "HIGHER" if avg_diff > 0 else "LOWER"
st.write(
    f"• **Positioning:** Client products average **£{abs(avg_diff):.2f}"
    f" {pos_direction}** than the market benchmark."
)

if overpriced_count > 0:
  st.write(
      f"• **Key Risk:** **{overpriced_count} product(s)** sit above market"
      " average price."
  )
if underpriced_count > 0:
  st.write(
      f"• **Opportunity:** **{underpriced_count} product(s)** sit below"
      " benchmark (margin expansion potential)."
  )

st.markdown("---")

# ==============================================================================
# 4. TABLES (ORIGINAL & RECOMMENDED STRATEGY)
# ==============================================================================
# Table 1: Original Audit Table
st.subheader("📋 Original Market Comparison Registry")
orig_cols = [
    col
    for col in ["Product", "Price (£)", comp_col, "Difference (£)"]
    if col in filtered_df.columns
]
st.dataframe(filtered_df[orig_cols], use_container_width=True)

# Table 2: Pricing Strategy Table with Rounded Recommended Price
st.subheader("🎯 Recommended Pricing Targets")
rec_cols = [
    col
    for col in [
        "Product",
        "Price (£)",
        comp_col,
        "Recommended Price (£)",
    ]
    if col in filtered_df.columns
]
# Format currency display explicitly
formatted_rec_df = filtered_df[rec_cols].copy()
if "Recommended Price (£)" in formatted_rec_df.columns:
  formatted_rec_df["Recommended Price (£)"] = formatted_rec_df[
      "Recommended Price (£)"
  ].map("£{:.2f}".format)

st.dataframe(formatted_rec_df, use_container_width=True)

# CSV Export Button
csv_data = filtered_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Download Full Audit Data (CSV)",
    data=csv_data,
    file_name="market_audit_data.csv",
    mime="text/csv",
)