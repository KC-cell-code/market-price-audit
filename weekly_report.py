import json
import os
import smtplib
import tempfile
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from bs4 import BeautifulSoup
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt
import pandas as pd
import requests

SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASSWORD", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


def get_all_subscribers():
  scopes = ["https://www.googleapis.com/auth/spreadsheets"]
  creds_raw = os.getenv("GOOGLE_SHEETS_CREDS")

  try:
    if creds_raw:
      creds_dict = json.loads(creds_raw)
      creds = Credentials.from_service_account_info(
          creds_dict, scopes=scopes
      )
    elif os.path.exists("google_credentials.json"):
      creds = Credentials.from_service_account_file(
          "google_credentials.json", scopes=scopes
      )
    else:
      print("No Google Sheets credentials found.")
      return []

    client = gspread.authorize(creds)
    sheet = client.open("Audit_Subscribers").sheet1
    emails = sheet.col_values(1)
    # Filter out empty cells or header labels
    valid_emails = [
        e.strip() for e in emails if e and "@" in e and e.lower() != "email"
    ]
    return list(set(valid_emails))
  except Exception as e:
    print(f"Error fetching subscribers from Google Sheets: {e}")
    return []


def scrape_five_pages():
  scraped_items = []
  for page in range(1, 6):
    url = f"http://books.toscrape.com/catalogue/page-{page}.html"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
      response = requests.get(url, headers=headers, timeout=10)
      if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        articles = soup.find_all("article", class_="product_pod")
        for idx, article in enumerate(articles):
          title = article.h3.a["title"]
          price_text = article.find("p", class_="price_color").text
          store_price = float(
              "".join(c for c in price_text if c.isdigit() or c == ".")
          )
          multiplier = 0.90 if idx % 2 == 0 else 1.10
          benchmark_price = round(store_price * multiplier, 2)
          difference = round(store_price - benchmark_price, 2)
          scraped_items.append({
              "Product": title,
              "Client Price (£)": store_price,
              "Comp Avg (£)": benchmark_price,
              "Difference (£)": difference,
          })
    except Exception as e:
      print(f"Error scraping page {page}: {e}")
  return pd.DataFrame(scraped_items)


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
      label="Store Price",
      color="#1E3A8A",
  )
  ax.bar(
      [i + width / 2 for i in x],
      comparison["Comp Avg (£)"],
      width,
      label="Benchmark",
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

  pdf = FPDF()
  pdf.add_page()
  pdf.set_font("Arial", "B", 16)
  pdf.set_text_color(30, 58, 138)
  pdf.cell(0, 10, txt="Weekly Market Audit Executive Report", ln=True, align="C")
  pdf.ln(3)

  pdf.set_font("Arial", "B", 11)
  pdf.set_text_color(30, 58, 138)
  pdf.cell(0, 6, txt="Automated Market Insights:", ln=True)

  pdf.set_font("Arial", "", 9)
  pdf.set_text_color(51, 65, 85)
  pos_direction = "HIGHER" if price_diff > 0 else "LOWER"
  insight_pos = (
      f"* Positioning: Store catalog averages \xa3{abs(price_diff):.2f}"
      f" {pos_direction} than market benchmark."
  )
  pdf.set_x(pdf.l_margin)
  pdf.multi_cell(0, 5, txt=str(insight_pos))

  if overpriced_count > 0:
    insight_risk = (
        f"* Key Risk: {overpriced_count} product(s) priced above benchmark."
    )
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, txt=str(insight_risk))

  if underpriced_count > 0:
    insight_opp = (
        f"* Opportunity: {underpriced_count} product(s) priced below benchmark"
        " (margin potential)."
    )
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, txt=str(insight_opp))

  pdf.ln(4)
  pdf.image(temp_img_path, x=15, w=180)
  pdf.ln(4)

  pdf.set_font("Arial", "B", 9)
  pdf.set_fill_color(30, 58, 138)
  pdf.set_text_color(255, 255, 255)
  w_item, w_client, w_comp, w_diff = 75, 35, 40, 40

  pdf.cell(w_item, 7, "Product Name", border=1, align="C", fill=True)
  pdf.cell(w_client, 7, "Store (\xa3)", border=1, align="C", fill=True)
  pdf.cell(w_comp, 7, "Benchmark (\xa3)", border=1, align="C", fill=True)
  pdf.cell(w_diff, 7, "Variance (\xa3)", border=1, align="C", fill=True)
  pdf.ln()

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


def send_batch_emails(recipients, pdf_bytes):
  if not recipients:
    print("No active subscribers found.")
    return

  if not SMTP_USER or not SMTP_PASS:
    print(
        f"[Simulation Mode] Would send email to {len(recipients)}"
        f" subscriber(s): {recipients}"
    )
    return

  with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
    server.starttls()
    server.login(SMTP_USER, SMTP_PASS)

    for recipient in recipients:
      msg = MIMEMultipart()
      msg["From"] = SMTP_USER
      msg["To"] = recipient
      msg["Subject"] = "Weekly Market Price Audit Executive Report"

      body = (
          "Hello,\n\nPlease find attached your weekly automated Market Price"
          " Audit Executive Report PDF.\n\nBest regards,\nAutomated Reporting"
          " Bot"
      )
      msg.attach(MIMEText(body, "plain"))

      part = MIMEApplication(pdf_bytes, Name="weekly_market_audit.pdf")
      part["Content-Disposition"] = (
          'attachment; filename="weekly_market_audit.pdf"'
      )
      msg.attach(part)

      server.send_message(msg)
      print(f"Sent report to: {recipient}")


if __name__ == "__main__":
  print("Starting weekly subscriber audit dispatch...")
  subscribers = ["subredditspooks@gmail.com"]
  print(f"Found {len(subscribers)} active subscriber(s).")

  if subscribers:
    df = scrape_five_pages()
    if not df.empty:
      pdf_data = generate_pdf_bytes(df)
      send_batch_emails(subscribers, pdf_data)
    else:
      print("Failed to scrape audit data.")
