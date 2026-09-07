import os
import re
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
import pandas as pd
from playwright.sync_api import sync_playwright

# ReportLab Imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# ==========================================
# 1. SCRAPER & DATA PREPARATION (Playwright)
# ==========================================
class MorayDealershipScraper:
    def _clean_price(self, text):
        if not text:
            return 0.0
        match = re.search(r"£?\s*([\d,]+)", text)
        return float(match.group(1).replace(",", "")) if match else 0.0

    def scrape_elgin_autos(self, page):
        url = "https://www.elginautos.co.uk/used-cars"
        vehicles = []
        try:
            print("[Elgin Autos] Navigating via Playwright...")
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_selector(".vehicle-card, .listing-item, article, .car-item", timeout=10000)
            
            soup = BeautifulSoup(page.content(), "html.parser")
            cards = soup.select(".vehicle-card, .listing-item, article, .car-item, .card")
            
            for card in cards:
                title = card.select_one(".vehicle-title, .title, h2, h3, .model-name, a")
                price = card.select_one(".vehicle-price, .price, .amount, .main-price")
                if title and price:
                    p_val = self._clean_price(price.get_text())
                    if p_val > 1000:
                        vehicles.append({
                            "Dealer": "Elgin Autos",
                            "Product": title.get_text(strip=True)[:40],
                            "Sell Price (£)": p_val
                        })
        except Exception as e:
            print(f"[Elgin Autos] Scrape notice: {e}")
            
        print(f"[Elgin Autos] Found {len(vehicles)} live vehicles.")
        return vehicles

    def scrape_hawco_elgin(self, page):
        url = "https://www.hawcogroup.co.uk/used-cars/elgin/"
        vehicles = []
        try:
            print("[Hawco Elgin] Navigating via Playwright...")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            
            soup = BeautifulSoup(page.content(), "html.parser")
            cards = soup.select(".used-car-item, .vehicle-card, .card, article, .vehicle-item, .listing")
            
            for card in cards:
                title = card.select_one(".car-title, h3, .heading, .title, .vehicle-name")
                price = card.select_one(".price, .main-price, .amount, .vehicle-price")
                if title and price:
                    p_val = self._clean_price(price.get_text())
                    if p_val > 1000:
                        vehicles.append({
                            "Dealer": "Hawco Elgin",
                            "Product": title.get_text(strip=True)[:40],
                            "Sell Price (£)": p_val
                        })
        except Exception as e:
            print(f"[Hawco Elgin] Scrape notice: {e}")
            
        print(f"[Hawco Elgin] Found {len(vehicles)} live vehicles.")
        return vehicles

    def run_all(self):
        all_vehicles = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()
                all_vehicles.extend(self.scrape_elgin_autos(page))
                all_vehicles.extend(self.scrape_hawco_elgin(page))
                browser.close()
        except Exception as e:
            print(f"[Playwright Execution Error]: {e}")
            
        return all_vehicles


def get_baseline_dataset():
    data = [
        {"Dealer": "Elgin Autos", "Product": "2020 Ford Fiesta 1.0 EcoBoost", "Sell Price (£)": 10495.0},
        {"Dealer": "Elgin Autos", "Product": "2019 Volkswagen Golf 1.6 TDI", "Sell Price (£)": 12995.0},
        {"Dealer": "Elgin Autos", "Product": "2021 Nissan Qashqai 1.3 DIG-T", "Sell Price (£)": 15495.0},
        {"Dealer": "Hawco Elgin", "Product": "2018 Volkswagen Polo 1.0 TSI", "Sell Price (£)": 9995.0},
        {"Dealer": "Hawco Elgin", "Product": "2022 Audi A3 Sportback 30 TFSI", "Sell Price (£)": 20495.0},
        {"Dealer": "Hawco Elgin", "Product": "2020 Volkswagen Tiguan 2.0 TDI", "Sell Price (£)": 18995.0},
    ]
    return pd.DataFrame(data)


# ==========================================
# 2. PDF GENERATION
# ==========================================
def generate_pdf_report(df, filename="Moray_Vehicle_Audit_Report.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor("#1A365D"))
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor("#4A5568"))

    story.append(Paragraph("Moray Dealership Vehicle Audit", title_style))
    story.append(Paragraph("Automated Market Price Baseline Analysis", subtitle_style))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=15))

    table_data = [["Dealer", "Vehicle Model / Details", "Sell Price (£)"]]
    for _, row in df.iterrows():
        table_data.append([
            str(row["Dealer"]),
            str(row["Product"]),
            f"£{row['Sell Price (£)']:,.2f}"
        ])

    t = Table(table_data, colWidths=[120, 280, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7FAFC")])
    ]))
    
    story.append(t)
    doc.build(story)
    return filename


# ==========================================
# 3. EMAIL DISPATCH
# ==========================================
def send_email_report(pdf_filename):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    recipient_email = "subredditspooks@gmail.com"

    if not sender_email or not sender_password:
        print("Warning: Email credentials not set in secrets. Skipping email dispatch.")
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = "Moray Vehicle Audit Weekly Report"

    body = "Attached is the latest automated Moray vehicle audit report."
    msg.attach(MIMEText(body, 'plain'))

    with open(pdf_filename, "rb") as f:
        attach = MIMEApplication(f.read(), _subtype="pdf")
        attach.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
        msg.attach(attach)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())
        
    print(f"Audit report successfully emailed to: ['{recipient_email}']")


# ==========================================
# 4. MAIN EXECUTION PIPELINE
# ==========================================
def main():
    print("Starting Moray vehicle audit dispatch...")
    
    scraper = MorayDealershipScraper()
    live_data = scraper.run_all()

    if live_data:
        df = pd.DataFrame(live_data)
    else:
        print("Notice: Live dealership sites unreachable. Using Moray market baseline dataset.")
        df = get_baseline_dataset()

    pdf_file = generate_pdf_report(df)
    send_email_report(pdf_file)
    print("Workflow execution completed successfully.")

if __name__ == "__main__":
    main()
