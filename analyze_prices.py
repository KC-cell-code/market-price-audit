import os
import re
import matplotlib.pyplot as plt
import pandas as pd
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF


# 1. SCRAPER FUNCTION (Dynamically extracts product titles)
def scrape_site_prices(url, shop_name):
  headers = {'User-Agent': 'Mozilla/5.0'}
  try:
    response = requests.get(url, headers=headers, timeout=5)
    soup = BeautifulSoup(response.text, 'html.parser')

    items = []
    for product in soup.find_all('article', class_='product_pod'):
      title = product.h3.a['title'].strip()
      price_text = product.find('p', class_='price_color').text
      price = float(re.sub(r'[^\d.]', '', price_text))

      items.append({'Shop': shop_name, 'Product': title, 'Price (£)': price})
    return pd.DataFrame(items)
  except Exception as e:
    print(f'Could not scrape {shop_name}: {e}')
    return pd.DataFrame()


# 2. LOAD TARGETS & SCRAPE ALL 5 STORES
targets_df = pd.read_csv('targets.csv')
scraped_dataframes = []

for _, row in targets_df.iterrows():
  print(f"Scraping {row['Shop']}...")
  df_shop = scrape_site_prices(row['URL'], row['Shop'])
  scraped_dataframes.append(df_shop)

master_df = pd.concat(scraped_dataframes, ignore_index=True)

# 3. SEPARATE CLIENT VS COMPETITORS
CLIENT_NAME = 'Our Client'

competitors_df = master_df[master_df['Shop'] != CLIENT_NAME]
client_df = master_df[master_df['Shop'] == CLIENT_NAME]

# Calculate overall market average per shop (if item names differ across shops)
comp_market_avg = competitors_df['Price (£)'].mean()
client_market_avg = client_df['Price (£)'].mean()

# Calculate per-product competitor average (for items with matching titles)
comp_avg_per_item = (
    competitors_df.groupby('Product')['Price (£)']
    .mean()
    .reset_index()
    .rename(columns={'Price (£)': 'Comp Avg (£)'})
)

# Merge client products with market averages
comparison = pd.merge(client_df, comp_avg_per_item, on='Product', how='inner')

# Fallback: If scraped items have unique names across shops, compare client products to overall market avg
if comparison.empty:
  comparison = client_df.copy()
  comparison['Comp Avg (£)'] = comp_market_avg

comparison['Difference (£)'] = (
    comparison['Price (£)'] - comparison['Comp Avg (£)']
).round(2)

# Limit comparison table/chart to top 8 items so the PDF stays clean
comparison = comparison.head(8)

# 4. GENERATE DYNAMIC INSIGHTS
overall_diff = client_market_avg - comp_market_avg
insights = []

if overall_diff > 0:
  insights.append(
      f'Overall Positioning: Client products average GBP {abs(overall_diff):.2f}'
      ' HIGHER than market average.'
  )
else:
  insights.append(
      f'Overall Positioning: Client products average GBP {abs(overall_diff):.2f}'
      ' LOWER than market average.'
  )

overpriced = comparison[comparison['Difference (£)'] > 0]
underpriced = comparison[comparison['Difference (£)'] < 0]

insights.append(
    f'Risk: {len(overpriced)} item(s) are priced above market benchmark.'
)
insights.append(
    f'Opportunity: {len(underpriced)} item(s) sit below benchmark, allowing'
    ' room for margin expansion.'
)


def clean_for_pdf(text):
  return str(text).encode('latin-1', 'replace').decode('latin-1')


# 5. GENERATE SLEEK CHART
plt.style.use('default')
fig, ax = plt.subplots(figsize=(10, 4.5))
fig.patch.set_facecolor('#ffffff')
ax.set_facecolor('#ffffff')

x = range(len(comparison))
width = 0.35

ax.bar(
    [i - width / 2 for i in x],
    comparison['Price (£)'],
    width,
    label='Our Client',
    color='#1E3A8A',
)
ax.bar(
    [i + width / 2 for i in x],
    comparison['Comp Avg (£)'],
    width,
    label='Market Benchmark',
    color='#64748B',
)

ax.set_title(
    'Product Price vs. Market Benchmark',
    fontsize=12,
    fontweight='bold',
    color='#0F172A',
)
ax.set_ylabel('Price (£)', fontsize=10, color='#475569')
ax.set_xticks(x)

# Truncate long product titles for graph labels
short_labels = [
    p[:12] + '...' if len(p) > 12 else p for p in comparison['Product']
]
ax.set_xticklabels(short_labels, fontsize=8, color='#0F172A', rotation=15)

ax.set_axisbelow(True)
ax.grid(axis='y', color='#E2E8F0', linestyle='--', alpha=0.8)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

legend = ax.legend(facecolor='#ffffff', edgecolor='#E2E8F0')
for text in legend.get_texts():
  text.set_color('#0F172A')

plt.tight_layout()
graph_file = 'temp_product_graph.png'
plt.savefig(graph_file, dpi=300, bbox_inches='tight')
plt.close()

# 6. BUILD DYNAMIC PDF
pdf = FPDF()
pdf.add_page()

pdf.set_font('Arial', 'B', 16)
pdf.cell(
    0, 10, txt='Market Intelligence & Competitive Audit', ln=True, align='C'
)
pdf.ln(3)

# Summary Box
pdf.set_fill_color(241, 245, 249)
pdf.rect(x=10, y=pdf.get_y(), w=190, h=35, style='F')

pdf.set_font('Arial', 'B', 10)
pdf.set_text_color(30, 58, 138)
pdf.cell(0, 6, txt='  EXECUTIVE SUMMARY & INSIGHTS', ln=True)

pdf.set_font('Arial', '', 9)
pdf.set_text_color(51, 65, 85)
for line in insights:
  pdf.cell(0, 6, txt=f'   - {clean_for_pdf(line)}', ln=True)

pdf.ln(8)
pdf.image(graph_file, x=15, y=pdf.get_y(), w=180)
pdf.ln(75)

# Detailed Table
pdf.set_font('Arial', 'B', 11)
pdf.set_text_color(15, 23, 42)
pdf.cell(0, 8, txt='Product Pricing Audit Table', ln=True)

pdf.set_fill_color(30, 58, 138)
pdf.set_text_color(255, 255, 255)
pdf.set_font('Arial', 'B', 9)

w_item, w_client, w_comp, w_diff = 75, 35, 40, 40

pdf.cell(w_item, 7, 'Product Title', border=1, align='C', fill=True)
pdf.cell(w_client, 7, 'Client (£)', border=1, align='C', fill=True)
pdf.cell(w_comp, 7, 'Benchmark (£)', border=1, align='C', fill=True)
pdf.cell(w_diff, 7, 'Variance (£)', border=1, align='C', fill=True)
pdf.ln()

pdf.set_font('Arial', '', 8)
pdf.set_text_color(51, 65, 85)

for idx, row in comparison.iterrows(): 
  diff_val = row['Difference (£)']
  diff_str = f'+{diff_val:.2f}' if diff_val > 0 else f'{diff_val:.2f}'
  title_truncated = clean_for_pdf(row['Product'])[:38]

  pdf.cell(w_item, 6, title_truncated, border=1, align='L')
  pdf.cell(w_client, 6, f"{row['Price (£)']:.2f}", border=1, align='C')
  pdf.cell(w_comp, 6, f"{row['Comp Avg (£)']:.2f}", border=1, align='C')
  pdf.cell(w_diff, 6, diff_str, border=1, align='C')
  pdf.ln()

pdf.output('Scraped_Market_Audit.pdf')

if os.path.exists(graph_file):
  os.remove(graph_file)

print('Updated PDF successfully generated as Scraped_Market_Audit.pdf!')