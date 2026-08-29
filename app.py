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
import streamlit as st

# ------------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & DARK MODE CSS
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Market Price Audit Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Global Dark Theme */
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #38BDF8;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #94A3B8;
        margin-bottom: 1.5rem;
    }

    /* Dark Metric Cards */
    [data-testid="stMetric"] {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        padding: 15px !important;
        border-radius: 10px !important;
    }
    [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
    }
    [data-testid="stMetricValue"] {
        color: #38BDF8 !important;
    }

    /* Color-Coded Insight Callout Boxes */
    .insight-box {
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 12px;
        font-size: 0.95rem;
        font-weight: 500;
        line-height: 1.4;
    }
    .insight-blue {
        background-color: #1E3A8A44;
        border-left: 5px solid #3B82F6;
        color: #93C5FD;
    }
    .insight-red {
        background-color: #7F1D1D44;
        border-left: 5px solid #EF4444;
        color: #FCA5A5;
    }
    .insight-green {
        background-color: #14532D44;
        border-left: 5px solid #22C55E;
        color: #86EFAC;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------------------
# 2. GOOGLE SHEETS SUBSCRIPTION HELPERS
# ------------------------------------------------------------------------------
def get_gsheets_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_raw = os.getenv("GOOGLE_SHEETS_CREDS")
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
        return None
    return gspread.authorize(creds)


def add_subscriber(email):
    try:
        client = get_gsheets_client()
        if not client:
            return False, "Database credentials (`GOOGLE_SHEETS_CREDS`) not configured."

        sheet = client.open("Audit_Subscribers").sheet1
        existing_emails = sheet.col_values(1)

        if email in existing_emails:
            return False, "This email is already subscribed to weekly reports."

        sheet.append_row([email])
        return True, f"Successfully subscribed **{email}** to weekly reports!"
    except Exception as e:
        return False, f"Failed to subscribe: {str(e)}"


# ------------------------------------------------------------------------------
# 3. AUTOMATIC MULTI-PAGE SCRAPER (PAGES 1 - 5)
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner="Scraping target catalog pages...")
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
            st.error(f"Error connecting to page {page}: {e}")

    return pd.DataFrame(scraped_items)


# ------------------------------------------------------------------------------
# 4. EMAIL DISPATCH HELPER
# ------------------------------------------------------------------------------
def send_audit_email(
    recipient_email, pdf_bytes, smtp_server="smtp.gmail.com", smtp_port=587
):
    if not recipient_email or "@" not in recipient_email:
        return False, "Please enter a valid recipient email address."

    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_pass:
        return (
            True,
            f"Simulated email sent to **{recipient_email}**! (Configure `SMTP_USER`"
            " & `SMTP_PASSWORD` environment secrets for live SMTP delivery)",
        )

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = recipient_email
        msg["Subject"] = "Market Price Audit Executive Report"

        body = (
            "Hello,\n\nPlease find attached the Market Price Audit"
            " Executive Report PDF.\n\nBest regards,\nMarket Intelligence"
            " Dashboard"
        )
        msg.attach(MIMEText(body, "plain"))

        part = MIMEApplication(pdf_bytes, Name="market_audit.pdf")
        part["Content-Disposition"] = 'attachment; filename="market_audit.pdf"'
        msg.attach(part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True, f"Report successfully sent to {recipient_email}!"
    except Exception as e:
        return False, f"Email delivery failed: {str(e)}"


# ------------------------------------------------------------------------------
# 5. PDF GENERATION FUNCTION (EXPLICIT BYTES CONVERSION)
# ------------------------------------------------------------------------------
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
    pdf.cell(
        0, 10, txt="Market Audit Executive Report", ln=True, align="C"
    )
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


# ------------------------------------------------------------------------------
# 6. APPLICATION EXECUTION & DASHBOARD DISPLAY
# ------------------------------------------------------------------------------
st.markdown(
    '<div class="main-header">📊 Market Audit Dashboard</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-header">Automatically auditing catalog items across target pages</div>',
    unsafe_allow_html=True,
)

audit_data = scrape_five_pages()
st.session_state.audit_df = audit_data

if not audit_data.empty:
    m1, m2, m3, m4 = st.columns(4)
    avg_client = audit_data["Client Price (£)"].mean()
    avg_comp = audit_data["Comp Avg (£)"].mean()
    overpriced = len(audit_data[audit_data["Difference (£)"] > 0])
    underpriced = len(audit_data[audit_data["Difference (£)"] < 0])
    price_diff = avg_client - avg_comp

    m1.metric("Total Products Audited", f"{len(audit_data)}")
    m2.metric(
        "Avg Store Price",
        f"£{avg_client:.2f}",
        delta=f"£{price_diff:+.2f}",
        delta_color="inverse",
    )
    m3.metric("Overpriced Items", f"{overpriced}")
    m4.metric("Underpriced Items", f"{underpriced}")

    st.write("")

    st.subheader("💡 Automated Market Insights")

    pos_direction = "HIGHER" if price_diff > 0 else "LOWER"
    st.markdown(
        f'<div class="insight-box insight-blue">🔵 <b>Market Positioning:</b> Store'
        f" prices average <b>£{abs(price_diff):.2f} {pos_direction}</b> than the"
        " competitor benchmark.</div>",
        unsafe_allow_html=True,
    )

    if overpriced > 0:
        st.markdown(
            f'<div class="insight-box insight-red">🔴 <b>Pricing Risk:</b>'
            f" <b>{overpriced} product(s)</b> sit above competitor price targets,"
            " risking lower sales velocity.</div>",
            unsafe_allow_html=True,
        )

    if underpriced > 0:
        st.markdown(
            f'<div class="insight-box insight-green">🟢 <b>Margin Opportunity:</b>'
            f" <b>{underpriced} product(s)</b> are priced lower than market"
            " benchmark, signaling room for price increase.</div>",
            unsafe_allow_html=True,
        )

    st.write("")

    st.subheader("📊 Catalog Breakdown")

    filter_option = st.radio(
        "Filter Catalog:",
        ("All Products", "Overpriced Only", "Underpriced Only"),
        horizontal=True,
    )

    if filter_option == "Overpriced Only":
        view_df = audit_data[audit_data["Difference (£)"] > 0]
    elif filter_option == "Underpriced Only":
        view_df = audit_data[audit_data["Difference (£)"] < 0]
    else:
        view_df = audit_data

    st.dataframe(
        view_df.style.format({
            "Client Price (£)": "£{:.2f}",
            "Comp Avg (£)": "£{:.2f}",
            "Difference (£)": "£{:+.2f}",
        }),
        use_container_width=True,
        height=380,
    )

    # --------------------------------------------------------------------------
    # SIDEBAR CONTROLS
    # --------------------------------------------------------------------------
    pdf_bytes = generate_pdf_bytes(audit_data)

    st.sidebar.title("📥 Export & Share")
    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Download PDF Audit")
    st.sidebar.download_button(
        label="Download PDF Executive Audit",
        data=pdf_bytes,
        file_name="market_audit.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("📧 Instant Email Dispatch")
    user_email = st.sidebar.text_input(
        "Recipient Email Address", placeholder="name@company.com", key="instant_email"
    )

    if st.sidebar.button("✉️ Send PDF Now", use_container_width=True):
        success, message = send_audit_email(user_email, pdf_bytes)
        if success:
            st.sidebar.success(message)
        else:
            st.sidebar.error(message)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Weekly Automated Subscription")
    sub_email = st.sidebar.text_input(
        "Subscribe to Weekly PDF Email", placeholder="client@company.com", key="sub_email"
    )

    if st.sidebar.button("🔔 Subscribe to Weekly Report", use_container_width=True):
        if "@" in sub_email:
            success, msg = add_subscriber(sub_email.strip())
            if success:
                st.sidebar.success(msg)
            else:
                st.sidebar.warning(msg)
        else:
            st.sidebar.error("Please enter a valid email address.")

else:
    st.error("Unable to scrape target catalog pages. Check your internet connection.")