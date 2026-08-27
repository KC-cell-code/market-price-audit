import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
# Import your custom scraping logic here
# from analyze_prices import run_scraper


def send_automated_report():
  # 1. Run Scraper / Read Data
  # df = run_scraper()
  df = pd.read_csv("targets.csv")  # Replace with actual scraped data source

  # 2. Extract Credentials & Recipient from Environment Variables
  sender_email = os.environ.get("ALERT_EMAIL_USER")
  sender_password = os.environ.get("ALERT_EMAIL_PASS")
  recipient_email = os.environ.get("CLIENT_EMAIL")

  if not sender_email or not sender_password or not recipient_email:
    print("Error: Missing email environment secrets.")
    return

  # 3. Calculate Insights
  # (Example threshold: products where client is undercut by competitors)
  overpriced = df[df["Difference (£)"] > 0] if "Difference (£)" in df else df

  if overpriced.empty:
    print("No price alerts detected. Skipping email dispatch.")
    return

  # 4. Build Email
  msg = MIMEMultipart("alternative")
  msg["Subject"] = "🗓️ Scheduled Market Intelligence Audit"
  msg["From"] = sender_email
  msg["To"] = recipient_email

  rows = ""
  for _, row in overpriced.iterrows():
    rows += f"<tr><td style='padding:8px;'>{row['Product']}</td><td style='padding:8px;'>£{row['Price (£)']:.2f}</td></tr>"

  html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h2>Automated Market Audit Update</h2>
        <p>The latest price scrape identified key items requiring pricing review:</p>
        <table border="1" style="border-collapse: collapse;">
            <tr style="background:#1E3A8A; color:white;"><th>Product</th><th>Client Price</th></tr>
            {rows}
        </table>
      </body>
    </html>
    """
  msg.attach(MIMEText(html_body, "html"))

  # 5. Dispatch Email
  try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
      server.login(sender_email, sender_password)
      server.sendmail(sender_email, recipient_email, msg.as_string())
    print(f"Scheduled report successfully delivered to {recipient_email}")
  except Exception as e:
    print(f"Failed to send scheduled email: {e}")


if __name__ == "__main__":
  send_automated_report()