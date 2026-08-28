import os
import smtplib
import tempfile
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from bs4 import BeautifulSoup
from fpdf import FPDF
import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st

# ------------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & DARK MODE CSS
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Market Price Audit Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Dark Mode Styling & Colored Insight Callout Containers
st.markdown(
    """
    <style>
    /* Dark Theme Core Styles */
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

    /* Color-Coded Executive Insight Boxes (Dark Mode) */
    .insight-box {
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 12px;
        font-size: 0.95rem;
        font-weight: 500;
        line-height: 1.4;
    }
    .insight-blue {
        background-color: #1E3A8A33;
        border-left: 5px solid #3B82F6;
        color: #93C5FD;
    }
    .insight-red {
        background-color: #7F1D1D33;
        border-left: 5px solid #EF4444;
        color: #FCA5A5;
    }
    .insight-green {
        background-color: #14532D33;
        border-left: 5px solid #22C55E;
        color: #86EFAC;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Initialize persistent session state
if "audit_df" not in st.session_state:
    st.session_state.audit_df = pd.DataFrame()


# ------------------------------------------------------------------------------
# 2. WEB SCRAPER FOR BOOK WEBSITE (books.toscrape.com)
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner="Scraping book website data...")
def scrape_book_website():
    url = "http://books.toscrape.com/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            st.error("Failed to fetch data from the book website.")
            return pd.DataFrame()

        soup = BeautifulSoup(response.content, "html.parser")
        articles = soup.find_all("article", class_="product_pod")

        scraped_data = []
        for article in articles:
            title = article.h3.a["title"]
            price_text = article.find("p", class_="price_color").text
            clean_price = float(
                "".join(c for c in price_text if c.isdigit() or c == ".")
            )
            benchmark_price = round(clean_price * 0.95, 2)

            scraped_data.append({
                "Book Title": title,
                "Store Price (£)": clean_price,
                "Market Benchmark (£)": benchmark_price,
            })

        return pd.DataFrame(scraped_data)
    except Exception as e:
        st.error(f"Error scraping site: {e}")
        return pd.DataFrame()


# ------------------------------------------------------------------------------
# 3. EMAIL DISPATCH HELPER
# ------------------------------------------------------------------------------
def send_audit_email(
        recipient_email, pdf_bytes, smtp_server="smtp.gmail.com", smtp_port=587
):
    if not recipient_email or "@" not in recipient_email:
        return False, "Please enter a valid recipient email address."

    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")

    # Fallback notification if environment credentials aren't configured yet
    if not smtp_user or not smtp_pass:
        return (
            True,
            f"Simulated email sent successfully to **{recipient_email}**! (Add"
            " `SMTP_USER` & `SMTP_PASSWORD` environment secrets for live delivery)",
        )

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = recipient_email
        msg["Subject"] = "Market Price Audit Executive Report"

        body = (
            "Hello,\n\nPlease find attached the generated Market Price Audit"
            " Executive Report PDF.\n\nBest regards,\nMarket Intelligence"
            " Dashboard"
        )
        msg.attach(MIMEText(body, "plain"))

        part = MIMEApplication(pdf_bytes, Name="market_audit_report.pdf")
        part["Content-Disposition"] = (
            'attachment; filename="market_audit_report.pdf"'
        )
        msg.attach(part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True, f"Report successfully dispatched to {recipient_email}!"
    except Exception as e:
        return False, f"Email delivery failed: {str(e)}"


# ------------------------------------------------------------------------------
# 4. PDF GENERATION (FIXED BYTE RETURN TYPE)
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

    # Export Chart Image (High contrast light background for clear PDF printing)
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
        label="Client Price",
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
    pdf.set_text_color(30, 58, 138)
    pdf.cell(
        0,
        10,
        txt="Market Intelligence & Competitive Audit",
        ln=True,
        align="C",
    )
    pdf.ln(3)

    # PDF Automated Insights
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 6, txt="Automated Market Insights:", ln=True)

    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(51, 65, 85)

    pos_direction = "HIGHER" if price_diff > 0 else "LOWER"
    insight_pos = (
        f"* Positioning: Client catalog averages \xa3{abs(price_diff):.2f}"
        f" {pos_direction} than market benchmark."
    )
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, txt=str(insight_pos))

    if overpriced_count > 0:
        insight_risk = (
            f"* Key Risk: {overpriced_count} product(s) priced above market"
            " benchmark."
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

    # PDF Table Headers
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    w_item, w_client, w_comp, w_diff = 75, 35, 40, 40

    pdf.cell(w_item, 7, "Product Title", border=1, align="C", fill=True)
    pdf.cell(w_client, 7, "Client (\xa3)", border=1, align="C", fill=True)
    pdf.cell(w_comp, 7, "Benchmark (\xa3)", border=1, align="C", fill=True)
    pdf.cell(w_diff, 7, "Variance (\xa3)", border=1, align="C", fill=True)
    pdf.ln()

    # Color-Coded Rows
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(0, 0, 0)

    for _, row in audit_df.iterrows():
        diff_val = row["Difference (£)"]
        diff_str = f"+{diff_val:.2f}" if diff_val > 0 else f"{diff_val:.2f}"
        clean_title = (
            str(row["Product"]).encode("latin-1", "replace").decode("latin-1")[:38]
        )

        if diff_val > 0:
            pdf.set_fill_color(254, 226, 226)  # Light Red
        elif diff_val < 0:
            pdf.set_fill_color(220, 252, 231)  # Light Green
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

    # Cast output directly to Python bytes
    return bytes(pdf.output())


# ------------------------------------------------------------------------------
# 5. SIDEBAR CONTROLS & DATA LOADING
# ------------------------------------------------------------------------------
st.sidebar.title("⚙️ Audit Controls")

data_source = st.sidebar.radio(
    "Data Source",
    ("Scrape Book Website", "Upload Spreadsheet", "Load Sample Catalog"),
)

raw_df = None

if data_source == "Scrape Book Website":
    st.sidebar.info("Scrapes live price data from `books.toscrape.com`.")
    if st.sidebar.button("🌐 Scrape Live Book Website"):
        raw_df = scrape_book_website()
        if not raw_df.empty:
            st.sidebar.success(f"Successfully scraped {len(raw_df)} books!")

elif data_source == "Upload Spreadsheet":
    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV or Excel file", type=["csv", "xlsx"]
    )
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                raw_df = pd.read_csv(uploaded_file)
            else:
                raw_df = pd.read_excel(uploaded_file)
            st.sidebar.success(f"Loaded {len(raw_df)} items.")
        except Exception as e:
            st.sidebar.error(f"Error loading file: {e}")

else:
    raw_df = pd.DataFrame({
        "Product Name": [
            "Wireless Ergonomic Mouse",
            "Mechanical RGB Keyboard",
            "27-inch 1440p Gaming Monitor",
            "USB-C Multi-Port Hub",
            "Noise-Canceling Headphones",
        ],
        "Our Price": [29.99, 85.00, 240.00, 45.00, 110.00],
        "Competitor Benchmark": [24.50, 89.99, 219.00, 49.99, 95.00],
    })

# ------------------------------------------------------------------------------
# 6. MAIN DASHBOARD UI
# ------------------------------------------------------------------------------
st.markdown(
    '<div class="main-header">📈 Market Price Audit Dashboard</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-header">Compare catalog prices against market benchmarks,'
    " identify pricing risks, and export executive reports.</div>",
    unsafe_allow_html=True,
)

if raw_df is not None and not raw_df.empty:
    with st.expander("🛠️ Column Mapping & Configuration", expanded=True):
        cols = list(raw_df.columns)
        c1, c2, c3 = st.columns(3)

        with c1:
            prod_col = st.selectbox("Product Title Column", cols, index=0)
        with c2:
            client_col = st.selectbox(
                "Client Price Column", cols, index=1 if len(cols) > 1 else 0
            )
        with c3:
            comp_col = st.selectbox(
                "Benchmark Price Column", cols, index=2 if len(cols) > 2 else 0
            )

        if st.button("🚀 Calculate Audit Data", type="primary"):
            processed_df = pd.DataFrame()
            processed_df["Product"] = raw_df[prod_col].astype(str)

            processed_df["Client Price (£)"] = pd.to_numeric(
                raw_df[client_col], errors="coerce"
            ).fillna(0.0)
            processed_df["Comp Avg (£)"] = pd.to_numeric(
                raw_df[comp_col], errors="coerce"
            ).fillna(0.0)
            processed_df["Difference (£)"] = (
                    processed_df["Client Price (£)"] - processed_df["Comp Avg (£)"]
            )

            # Persist in session_state
            st.session_state.audit_df = processed_df
            st.rerun()

# ------------------------------------------------------------------------------
# 7. DASHBOARD DISPLAY, INSIGHT BOXES & EXPORTS
# ------------------------------------------------------------------------------
if "audit_df" in st.session_state and not st.session_state.audit_df.empty:
    audit_data = st.session_state.audit_df

    st.markdown("---")

    # Metric Cards
    m1, m2, m3, m4 = st.columns(4)
    avg_client = audit_data["Client Price (£)"].mean()
    avg_comp = audit_data["Comp Avg (£)"].mean()
    overpriced = len(audit_data[audit_data["Difference (£)"] > 0])
    underpriced = len(audit_data[audit_data["Difference (£)"] < 0])
    price_diff = avg_client - avg_comp

    m1.metric("Avg Client Price", f"£{avg_client:.2f}")
    m2.metric(
        "Avg Benchmark",
        f"£{avg_comp:.2f}",
        delta=f"£{price_diff:+.2f}",
        delta_color="inverse",
    )
    m3.metric("Overpriced Items", f"{overpriced}")
    m4.metric("Underpriced Items", f"{underpriced}")

    st.write("")

    # COLOR-CODED EXECUTIVE INSIGHT CALLOUT BOXES
    st.subheader("💡 Automated Market Insights")

    pos_direction = "HIGHER" if price_diff > 0 else "LOWER"
    st.markdown(
        f'<div class="insight-box insight-blue">🔵 <b>Market Positioning:</b> Your'
        f" product catalog averages <b>£{abs(price_diff):.2f} {pos_direction}</b>"
        " than the market benchmark.</div>",
        unsafe_allow_html=True,
    )

    if overpriced > 0:
        st.markdown(
            f'<div class="insight-box insight-red">🔴 <b>Pricing Risk:</b>'
            f" <b>{overpriced} product(s)</b> are currently priced above market"
            " benchmark, risking potential lost conversions.</div>",
            unsafe_allow_html=True,
        )

    if underpriced > 0:
        st.markdown(
            f'<div class="insight-box insight-green">🟢 <b>Margin Opportunity:</b>'
            f" <b>{underpriced} product(s)</b> sit below competitor benchmark,"
            " presenting margin capture opportunities.</div>",
            unsafe_allow_html=True,
        )

    st.write("")

    # Table Filtering & Display
    st.subheader("📊 Audit Data Breakdown")

    filter_option = st.radio(
        "Filter View:",
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
        height=320,
    )

    # Sidebar Export & Email Features
    pdf_bytes = generate_pdf_bytes(audit_data)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Export Report")
    st.sidebar.download_button(
        label="Download PDF Market Audit",
        data=pdf_bytes,
        file_name="market_audit_report.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("📧 Email Audit Report")
    user_email = st.sidebar.text_input(
        "Recipient Email Address", placeholder="name@company.com"
    )

    if st.sidebar.button("✉️ Send Audit Email", use_container_width=True):
        success, message = send_audit_email(user_email, pdf_bytes)
        if success:
            st.sidebar.success(message)
        else:
            st.sidebar.error(message)

else:
    st.info(
        "👈 Select a data source from the sidebar and click **Calculate Audit"
        " Data** to render results."
    )