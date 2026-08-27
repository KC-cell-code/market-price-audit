name: Scheduled Market Audit

on:
  schedule:
    # Runs every Monday at 09:00 UTC (Weekly)
    # For Fortnightly: Handled inside Python or run on 1st & 15th ('0 9 1,15 * *')
    - cron: '0 9 * * 1'
  workflow_dispatch: # Allows manual trigger from GitHub UI

jobs:
  run-scraper-and-email:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt

      - name: Execute Scraper & Dispatch Alert
        env:
          ALERT_EMAIL_USER: ${{ secrets.ALERT_EMAIL_USER }}
          ALERT_EMAIL_PASS: ${{ secrets.ALERT_EMAIL_PASS }}
        run: python scheduled_runner.py