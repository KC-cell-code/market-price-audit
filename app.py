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
# 5. MAIN DASHBOARD CONTENT
# ==============================================================================
st.title("📊 Market Intelligence Dashboard")
st.markdown("Real-time price monitoring across competitors and client data.")

client_name = "Our Client"
client_data = filtered_df[filtered_df["Shop"] == client_name]
comp_data = filtered_df[filtered_df["Shop"] != client_name]

# 1. TOP METRICS
col1, col2, col3 = st.columns(3)

client_avg = (
    client_data["Price (£)"].mean() if not client_data.empty else 0.0
)
comp_avg = comp_data["Price (£)"].mean() if not comp_data.empty else 0.0
diff = client_avg - comp_avg

col1.metric("Client Avg Price", f"£{client_avg:.2f}")
col2.metric("Market Benchmark Avg", f"£{comp_avg:.2f}")

delta_val = f"+{diff:.2f}" if diff > 0 else f"{diff:.2f}"

col3.metric(
    "Price Variance",
    f"£{abs(diff):.2f}",
    delta=delta_val,
    delta_color="inverse",
)

# ==============================================================================
# 2. DYNAMIC INSIGHTS CARDS (NEW)
# ==============================================================================
st.subheader("💡 Automated Market Insights")

if not client_data.empty and not comp_data.empty:
  # Compute product-level differences
  comp_avg_per_item = (
      comp_data.groupby("Product")["Price (£)"]
      .mean()
      .reset_index()
      .rename(columns={"Price (£)": "Comp Avg (£)"})
  )
  merged_insights = pd.merge(
      client_data, comp_avg_per_item, on="Product", how="inner"
  )

  if merged_insights.empty:
    merged_insights = client_data.copy()
    merged_insights["Comp Avg (£)"] = comp_avg

  merged_insights["Difference (£)"] = (
          merged_insights["Price (£)"] - merged_insights["Comp Avg (£)"]
  )
  overpriced_items = merged_insights[merged_insights["Difference (£)"] > 0]
  underpriced_items = merged_insights[merged_insights["Difference (£)"] < 0]

  ins_col1, ins_col2 = st.columns(2)

  with ins_col1:
    if diff > 0:
      st.info(
          f"**Market Positioning:** Client products average **£{abs(diff):.2f}"
          " HIGHER** than the benchmark."
      )
    else:
      st.info(
          f"**Market Positioning:** Client products average **£{abs(diff):.2f}"
          " LOWER** than the benchmark."
      )

  with ins_col2:
    if len(overpriced_items) > 0:
      st.warning(
          f"**Key Risk:** {len(overpriced_items)} product(s) are priced above"
          " market benchmark."
      )
    if len(underpriced_items) > 0:
      st.success(
          f"**Growth Opportunity:** {len(underpriced_items)} product(s) sit"
          " below benchmark—room to optimize margins."
      )
else:
  st.warning(
      "Select both **Our Client** and at least one competitor store in the"
      " sidebar to view market insights."
  )

st.divider()

# ==============================================================================
# MAIN SECTION: ON-DEMAND EMAIL REPORTING
# ==============================================================================
st.divider()
st.subheader("📩 Distribute Market Intelligence Report")
st.markdown(
    "Send an automated email breakdown of current price variances and key risks"
    " directly to stakeholders."
)

# Create a clean side-by-side layout for input and action button
email_col1, email_col2 = st.columns([3, 1])

with email_col1:
  recipient_email = st.text_input(
      "Recipient Email Address",
      value="client@example.com",
      placeholder="Enter client email address...",
  )

with email_col2:
  # Vertically space the button to align with the text input field
  st.write("")
  st.write("")
if st.button("📧 Send Email Report", use_container_width=True):
  overpriced = merged_insights[merged_insights["Difference (£)"] > 0]
  if not overpriced.empty:
    email_sent = send_price_alert(overpriced, recipient_email)
    if email_sent:
      st.success(
          f"Audit report successfully delivered to **{recipient_email}**!"
      )
  else:
    st.info("No overpriced items detected. Client pricing is competitive!")

# 3. VISUAL CHART & DATA TABLE
left_col, right_col = st.columns([1, 1])

with left_col:
  st.subheader("Price Distribution by Store")
  fig, ax = plt.subplots(figsize=(7, 4))
  shop_averages = filtered_df.groupby("Shop")["Price (£)"].mean()

  colors = [
      "#1E3A8A" if s == client_name else "#64748B" for s in shop_averages.index
  ]
  ax.bar(shop_averages.index, shop_averages.values, color=colors)
  ax.set_ylabel("Average Price (£)")
  ax.spines["top"].set_visible(False)
  ax.spines["right"].set_visible(False)
  plt.xticks(rotation=20, ha="right")
  st.pyplot(fig)

with right_col:
  st.subheader("Scraped Product Registry")
  st.dataframe(
      filtered_df,
      column_config={
          "Price (£)": st.column_config.NumberColumn(format="£%.2f")
      },
      use_container_width=True,
      hide_index=True,
  )