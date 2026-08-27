import os
import re
import smtplib
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from bs4 import BeautifulSoup
from fpdf import FPDF
import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st

# ==============================================================================
# 1. PAGE SETUP
# ==============================================================================
st.set_page_config(
    page_title="Market Price Audit Dashboard",
    page_icon="📊",
    layout="wide",
)


# ==============================================================================
# 2. EMAIL ALERT HELPER FUNCTION
# ==============================================================================
def send_price_alert(overpriced_df, recipient_email):
  """Sends an HTML email alert when competitor prices undercut client prices."""
  if overpriced_df.empty:
    st.info("No price drops detected. Skipping email alert.")
    return False

  sender_email = os.environ.get("ALERT_EMAIL_USER", "krccjc8@gmail.com")
  sender_password = os.environ.get("ALERT_EMAIL_PASS", "bhhsqantckaklpvz")

  msg = MIMEMultipart("alternative")
  msg["Subject"] = "🚨 Market Alert: Competitors Undercutting Client Prices"
  msg["From"] = sender_email
  msg["To"] = recipient_email

  table_rows = ""
  for _, row in overpriced_df.iterrows():
    table_rows += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{row['Product']}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">£{row['Client Price (£)']:.2f}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center; color: #dc2626;">£{row['Comp Avg (£)']:.2f}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: bold; color: #dc2626;">+£{row['Difference (£)']:.2f}</td>
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


# ==============================================================================
# 3. PDF GENERATION HELPER FUNCTION WITH COLOR-CODED ROWS
# ==============================================================================
def generate_pdf_bytes(audit_df):
  if audit_df.empty:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "No audit data available for PDF generation.", ln=True)
    return bytes(pdf.output())  # <--- FIXED HERE

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
      p[:12] + "..." if len(p) > 12 else p for p in comparison["Product"]
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
  pdf.multi_cell(0, 5, text=str(insight_pos))

  if overpriced_count > 0:
    insight_risk = (
        f"* Key Risk: {overpriced_count} product(s) sit above market average."
    )
    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, text=str(insight_risk))

  if underpriced_count > 0:
    insight_opp = (
        f"* Opportunity: {underpriced_count} product(s) sit below benchmark"
        " (margin potential)."
    )
    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, text=str(insight_opp))

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
# 4. LIVE SCRAPER FUNCTION
# ==============================================================================
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

  return (
      pd.concat(scraped_dataframes, ignore_index=True)
      if scraped_dataframes
      else pd.DataFrame()
  )


with st.spinner("Scraping live target sites..."):
  df = load_and_scrape_data()

# ==============================================================================
# 5. SIDEBAR CONTROLS & ADVANCED FILTERS
# ==============================================================================
st.sidebar.header("Filter Options")

all_shops = list(df["Shop"].unique()) if not df.empty else []

# Client Store Selection
client_shop = st.sidebar.selectbox(
    "Select Your Store (Client)",
    options=all_shops,
    index=0 if all_shops else 0,
)

# Competitor Store Selection
comp_shops_options = [s for s in all_shops if s != client_shop]
selected_comps = st.sidebar.multiselect(
    "Select Competitor Stores",
    options=comp_shops_options,
    default=comp_shops_options,
)

# Advanced Search & Price Sliders
st.sidebar.markdown("---")
st.sidebar.subheader("Advanced Filters")

search_query = st.sidebar.text_input("Search Product Title", "")

min_p = float(df["Price (£)"].min()) if not df.empty else 0.0
max_p = float(df["Price (£)"].max()) if not df.empty else 100.0
price_range = st.sidebar.slider(
    "Filter by Price (£)",
    min_value=min_p,
    max_value=max_p,
    value=(min_p, max_p),
)

target_margin = st.sidebar.slider(
    "Target Profit Margin (%)", min_value=5, max_value=50, value=15
)

# ==============================================================================
# 6. DATA PROCESSING & METRICS COMPUTATION
# ==============================================================================
filtered_df = df[
    (df["Price (£)"] >= price_range[0]) & (df["Price (£)"] <= price_range[1])
].copy()

if search_query:
  filtered_df = filtered_df[
      filtered_df["Product"].str.contains(search_query, case=False, na=False)
  ]

client_df = filtered_df[filtered_df["Shop"] == client_shop]
comp_df = filtered_df[filtered_df["Shop"].isin(selected_comps)]

if not client_df.empty and not comp_df.empty:
  comp_avg = (
      comp_df.groupby("Product")["Price (£)"]
      .mean()
      .reset_index()
      .rename(columns={"Price (£)": "Comp Avg (£)"})
  )

  audit_df = pd.merge(
      client_df[["Product", "Price (£)"]].rename(
          columns={"Price (£)": "Client Price (£)"}
      ),
      comp_avg,
      on="Product",
      how="inner",
  )

  audit_df["Client Price (£)"] = audit_df["Client Price (£)"].round(2)
  audit_df["Comp Avg (£)"] = audit_df["Comp Avg (£)"].round(2)
  audit_df["Difference (£)"] = (
      audit_df["Client Price (£)"] - audit_df["Comp Avg (£)"]
  ).round(2)
  audit_df["Recommended Price (£)"] = (
      audit_df["Comp Avg (£)"] * (1 + (target_margin / 100))
  ).round(2)
else:
  audit_df = pd.DataFrame(
      columns=[
          "Product",
          "Client Price (£)",
          "Comp Avg (£)",
          "Difference (£)",
          "Recommended Price (£)",
      ]
  )

# Compute Core Metrics
total_audited = len(audit_df)
avg_client_price = (
    audit_df["Client Price (£)"].mean() if total_audited > 0 else 0.0
)
avg_market_price = (
    audit_df["Comp Avg (£)"].mean() if total_audited > 0 else 0.0
)

overpriced_df = (
    audit_df[audit_df["Difference (£)"] > 0] if total_audited > 0 else audit_df
)
underpriced_df = (
    audit_df[audit_df["Difference (£)"] < 0] if total_audited > 0 else audit_df
)

overpriced_count = len(overpriced_df)
underpriced_count = len(underpriced_df)
avg_diff = audit_df["Difference (£)"].mean() if total_audited > 0 else 0.0

# Sidebar Downloads
st.sidebar.markdown("---")
st.sidebar.subheader("Export & Alerts")

pdf_data = generate_pdf_bytes(audit_df)
st.sidebar.download_button(
    label="📄 Download PDF Market Audit",
    data=pdf_data,
    file_name="Market_Intelligence_Report.pdf",
    mime="application/pdf",
    use_container_width=True,
)

# ==============================================================================
# 7. DASHBOARD HEADER & ALL 6 METRIC CARDS
# ==============================================================================
st.title("📊 Market Intelligence & Audit Dashboard")

st.subheader("Overview Metrics")
col1, col2, col3 = st.columns(3)
col1.metric("Total Products Audited", total_audited)
col2.metric("Avg Client Price", f"£{avg_client_price:.2f}")
col3.metric("Avg Market Price", f"£{avg_market_price:.2f}")

col4, col5, col6 = st.columns(3)
col4.metric(
    "Overpriced Items (Risk)",
    overpriced_count,
    delta=f"{overpriced_count} items",
    delta_color="inverse",
)
col5.metric(
    "Underpriced Items (Opportunity)",
    underpriced_count,
    delta=f"{underpriced_count} items",
)
col6.metric(
    "Avg Price Difference",
    f"£{abs(avg_diff):.2f}",
    delta=f"{'Above' if avg_diff > 0 else 'Below'} Market",
    delta_color="inverse",
)

st.markdown("---")

# ==============================================================================
# 8. RESTORED DYNAMIC EXECUTIVE INSIGHTS
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
# 9. COLOR-CODED TABLES (ORIGINAL & STRATEGY TARGETS)
# ==============================================================================


# Color styling function for Streamlit DataFrames
def style_difference(val):
  if val > 0:
    return (
        "background-color: #fee2e2; color: #991b1b; font-weight: bold;"
    )  # Red
  elif val < 0:
    return (
        "background-color: #dcfce7; color: #166534; font-weight: bold;"
    )  # Green
  return ""


st.subheader("📋 Original Market Comparison Registry")
orig_display = audit_df[
    ["Product", "Client Price (£)", "Comp Avg (£)", "Difference (£)"]
]
st.dataframe(
    orig_display.style.map(style_difference, subset=["Difference (£)"]),
    use_container_width=True,
)

st.subheader("🎯 Recommended Pricing Targets")
rec_display = audit_df[
    ["Product", "Client Price (£)", "Comp Avg (£)", "Recommended Price (£)"]
]
st.dataframe(rec_display, use_container_width=True)

csv_data = audit_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Download Full Audit Data (CSV)",
    data=csv_data,
    file_name="market_audit_data.csv",
    mime="text/csv",
)

# ==============================================================================
# 10. EMAIL REPORT DISPATCH SECTION
# ==============================================================================
st.markdown("---")
st.subheader("📧 Dispatch Email Report")
recipient_email = st.text_input(
    "Recipient Email Address", value="client@example.com"
)
if st.button("✉️ Send Market Alert Email"):
  success = send_price_alert(overpriced_df, recipient_email)
  if success:
    st.success(f"Audit report successfully delivered to **{recipient_email}**!")