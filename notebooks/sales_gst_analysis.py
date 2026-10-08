# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.6
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Amazon India Sales & GST Analytics (Mar–Jun 2022)
#
# **Goal:** turn ~1.29 lakh raw Amazon India apparel order lines into answers a business and its accounts team can act on:
#
# 1. How much did we really sell (after cancellations and returns), and is it growing?
# 2. Which categories and states drive revenue?
# 3. Where are we losing orders (cancellations, returns), and does fulfilment method matter?
# 4. What is our estimated GST liability, by rate slab and by CGST / SGST / IGST?
#
# **Tools:** Python (Pandas, Matplotlib) · SQL (SQLite, see `sql/`) · Excel (see `excel/`) · interactive dashboard (see `docs/`)

# %%
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
import clean_data as cd

IMG = ROOT / "images"; IMG.mkdir(exist_ok=True)
pd.set_option("display.float_format", lambda x: f"{x:,.2f}")

# Chart style: one blue for single series, recessive grid
BLUE, ORANGE, INK, MUTED, GRID, SURFACE = "#2a78d6", "#eb6834", "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": "#c3c2b7",
    "axes.labelcolor": "#52514e", "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
    "figure.dpi": 110, "axes.axisbelow": True, "savefig.bbox": "tight", "font.size": 10,
})
def inr_lakh(x, _=None):  # format rupees as lakh
    return f"₹{x/1e5:,.0f}L"



# %% [markdown]
# ## 1. Load raw data & check quality

# %%
raw = cd.load_raw()
print(raw.shape)
raw.head(3)

# %%
quality = pd.DataFrame({
    "missing": raw.isna().sum(),
    "missing_%": (raw.isna().mean() * 100).round(2),
}).query("missing > 0").sort_values("missing", ascending=False)
print("Exact duplicate rows:", raw.drop(columns=["index"]).duplicated().sum())
print("Raw status values:", raw["Status"].nunique())
print("Raw state spellings:", raw["ship-state"].str.strip().str.upper().nunique())
quality

# %% [markdown]
# **Issues found**
#
# * `Amount` is missing on ~6% of rows — almost all of them **cancelled** orders (nothing was charged), so they are set to 0, not dropped.
# * 13 different order statuses → grouped into 5 business groups (Shipped/Delivered, Cancelled, Returned, Pending, Lost/Damaged).
# * State names have typos and abbreviations (`RAJSHTHAN`, `RJ`, `ORISSA`, `NEW DELHI`, `PB` …) → standardised.
# * 6 exact duplicate rows → removed. Two fully empty / free-text columns → dropped (kept a simple *has_promotion* flag).
# * Date is text in `MM-DD-YY` format → converted to a real date.

# %% [markdown]
# ## 2. Clean & enrich (logic lives in `src/clean_data.py`)

# %%
df = cd.clean(raw)
print(f"{len(raw):,} raw rows -> {len(df):,} clean rows")
print("States after cleanup:", df.ship_state.nunique())
df[["order_id","order_date","category","qty","amount","status_group","ship_state","gst_rate","taxable_value","gst_amount","supply_type"]].head()

# %% [markdown]
# **Definition used everywhere:** *Net sales* = order lines that were **shipped or delivered**, with quantity ≥ 1 and amount > 0
# (cancelled, returned, pending and lost orders are excluded).

# %%
net = df[df.is_net_sale]
kpi = pd.Series({
    "Order lines (all)": len(df),
    "Net sales (₹)": net.amount.sum(),
    "Net orders": net.order_id.nunique(),
    "Units sold": net.qty.sum(),
    "Avg order value (₹)": net.groupby("order_id").amount.sum().mean(),
    "Cancellation rate (%)": (df.status_group == "Cancelled").mean() * 100,
    "Return rate (%)": (df.status_group == "Returned").mean() * 100,
    "Estimated GST (₹)": net.gst_amount.sum(),
})
kpi.to_frame("value")

# %% [markdown]
# ## 3. Sales trend

# %%
# 31 Mar (1 day) and 29 Jun (partial last day) are excluded from trend analysis
trend = net[(net.order_date >= "2022-04-01") & (net.order_date <= "2022-06-28")]
daily = trend.groupby("order_date").amount.sum()
roll = daily.rolling(7).mean()
fig, ax = plt.subplots(figsize=(10, 3.8))
ax.plot(daily.index, daily.values, color=BLUE, alpha=.35, lw=1.2, label="Daily net sales")
ax.plot(roll.index, roll.values, color=BLUE, lw=2.2, label="7-day average")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(inr_lakh))
ax.set_title("Daily net sales, 1 Apr – 28 Jun 2022")
ax.legend(frameon=False, loc="upper right")
fig.savefig(IMG / "01_daily_sales.png"); plt.show()

monthly = trend.groupby("order_month").agg(
    net_sales=("amount", "sum"), orders=("order_id", "nunique"), days=("order_date", "nunique"))
monthly["sales_per_day"] = monthly.net_sales / monthly.days
monthly["mom_change_%"] = (monthly.net_sales.pct_change() * 100).round(1)
monthly

# %% [markdown]
# *The data has only one day of March (31 Mar) and a partial last day (29 Jun), so trends use 1 Apr – 28 Jun. The per-day column keeps months of different length comparable.*

# %% [markdown]
# ## 4. Category performance

# %%
cat = net.groupby("category").agg(net_sales=("amount","sum"), units=("qty","sum")).sort_values("net_sales")
cat["share_%"] = cat.net_sales / cat.net_sales.sum() * 100
fig, ax = plt.subplots(figsize=(8, 4))
ax.barh(cat.index, cat.net_sales, color=BLUE, height=.6)
for y, (v, s) in enumerate(zip(cat.net_sales, cat["share_%"])):
    ax.text(v, y, f"  {s:.1f}%", va="center", fontsize=9, color="#52514e")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(inr_lakh)); ax.grid(axis="y", visible=False)
ax.set_title("Net sales by category")
fig.savefig(IMG / "02_category_sales.png"); plt.show()
cat.sort_values("net_sales", ascending=False)

# %% [markdown]
# ## 5. Where are customers? (state-wise)

# %%
state = net.groupby("ship_state").agg(net_sales=("amount","sum"), orders=("order_id","nunique")).sort_values("net_sales", ascending=False)
state["share_%"] = state.net_sales / state.net_sales.sum() * 100
state["cum_share_%"] = state["share_%"].cumsum()
top10 = state.head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.barh(top10.index.str.title(), top10.net_sales, color=BLUE, height=.6)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(inr_lakh)); ax.grid(axis="y", visible=False)
ax.set_title("Top 10 states by net sales")
fig.savefig(IMG / "03_top_states.png"); plt.show()
print(f"Top 5 states = {state['share_%'].head(5).sum():.1f}% of net sales")
state.head(10)

# %% [markdown]
# ## 6. Cancellations & returns

# %%
status = df.status_group.value_counts()
canc_by_fulfil = df.groupby("fulfilment").apply(lambda g: (g.status_group == "Cancelled").mean() * 100).rename("cancellation_%")
canc_by_cat = df.groupby("category").apply(lambda g: (g.status_group == "Cancelled").mean() * 100).rename("cancellation_%").sort_values(ascending=False)
fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
s = (status / status.sum() * 100).sort_values()
axes[0].barh(s.index, s.values, color=BLUE, height=.6); axes[0].set_title("Order lines by status (%)")
for y, v in enumerate(s.values): axes[0].text(v, y, f" {v:.1f}%", va="center", fontsize=9, color="#52514e")
axes[1].bar(canc_by_fulfil.index, canc_by_fulfil.values, color=BLUE, width=.5); axes[1].set_title("Cancellation rate by fulfilment (%)")
for x, v in enumerate(canc_by_fulfil.values): axes[1].text(x, v, f"{v:.1f}%", ha="center", va="bottom", fontsize=9, color="#52514e")
for a in axes: a.grid(axis="y" if a is axes[0] else "x", visible=False)
fig.tight_layout(); fig.savefig(IMG / "04_cancellations.png"); plt.show()
canc_by_fulfil.to_frame()

# %% [markdown]
# **Read:** orders fulfilled by the merchant (Easy Ship) are cancelled noticeably more often than orders fulfilled by Amazon (FBA).
# Moving fast-selling SKUs into FBA is a direct lever to cut lost sales.

# %% [markdown]
# ## 7. GST analysis

# %% [markdown]
# **Assumptions** (see `src/clean_data.py`):
# * `Amount` is GST-inclusive (Indian marketplace prices include GST).
# * Apparel GST in 2022: **5%** if the price per piece is ≤ ₹1,000, else **12%**.
# * Seller is registered in **Maharashtra** (not in the data — configurable). Orders shipped inside Maharashtra = CGST + SGST; all other states = IGST.

# %%
slab = net.groupby("gst_rate").agg(lines=("amount","size"), gross_sales=("amount","sum"),
                                   taxable_value=("taxable_value","sum"), gst=("gst_amount","sum"))
slab.index = [f"{r:.0%}" for r in slab.index]
slab["share_of_sales_%"] = slab.gross_sales / slab.gross_sales.sum() * 100
slab

# %%
split = pd.Series({"CGST": net.cgst.sum(), "SGST": net.sgst.sum(), "IGST": net.igst.sum()})
gst_state = net.groupby("ship_state").gst_amount.sum().sort_values(ascending=False).head(10).iloc[::-1]
fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8), gridspec_kw={"width_ratios": [1, 1.6]})
axes[0].bar(split.index, split.values, color=BLUE, width=.5); axes[0].set_title("Estimated GST by component")
for x, v in enumerate(split.values): axes[0].text(x, v, f"₹{v/1e5:,.1f}L", ha="center", va="bottom", fontsize=9, color="#52514e")
axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(inr_lakh)); axes[0].grid(axis="x", visible=False)
axes[1].barh(gst_state.index.str.title(), gst_state.values, color=BLUE, height=.6)
axes[1].set_title("Estimated GST by place of supply (top 10)")
axes[1].xaxis.set_major_formatter(mticker.FuncFormatter(inr_lakh)); axes[1].grid(axis="y", visible=False)
fig.tight_layout(); fig.savefig(IMG / "05_gst.png"); plt.show()
print(f"IGST share of total GST: {split.IGST / split.sum() * 100:.1f}%")
split.to_frame("₹")

# %% [markdown]
# ## 8. B2B vs B2C and sizes

# %%
b2b = net.groupby(net.is_b2b.map({True: "B2B", False: "B2C"})).agg(
    lines=("amount","size"), net_sales=("amount","sum"), avg_line_value=("amount","mean"))
size_order = ["XS","S","M","L","XL","XXL","3XL","4XL","5XL","6XL","Free"]
size = net.groupby("size").qty.sum().reindex(size_order).dropna()
display(b2b)
size.to_frame("units").T

# %% [markdown]
# ## 9. Key findings & recommendations
#
# Numbers below are produced by the cells above.

# %%
apr, jun = monthly.loc["2022-04"], monthly.loc["2022-06"]
findings = [
    f"Net sales of ₹{net.amount.sum()/1e7:.2f} crore from {net.order_id.nunique():,} orders (avg order value ₹{kpi['Avg order value (₹)']:,.0f}).",
    f"Sales per day fell {(1 - jun.sales_per_day / apr.sales_per_day) * 100:.1f}% from April to June — the trend needs attention.",
    f"'Set' and 'Kurta' bring in {cat.loc[['Set','Kurta'],'share_%'].sum():.1f}% of revenue — stock and ads should prioritise them.",
    f"Top 5 states (Maharashtra, Karnataka, Telangana, UP, Tamil Nadu) = {state['share_%'].head(5).sum():.1f}% of sales.",
    f"{kpi['Cancellation rate (%)']:.1f}% of order lines are cancelled; merchant-fulfilled orders cancel at {canc_by_fulfil['Merchant']:.1f}% vs {canc_by_fulfil['Amazon']:.1f}% for Amazon-fulfilled.",
    f"Estimated GST liability ₹{net.gst_amount.sum()/1e5:.1f} lakh; {slab.loc['5%','share_of_sales_%']:.1f}% of sales fall in the 5% slab and {split.IGST/split.sum()*100:.1f}% of GST is IGST (inter-state).",
]
for i, f in enumerate(findings, 1):
    print(f"{i}. {f}")

# %% [markdown]
# **Recommendations**
# 1. **Cut merchant-side cancellations** — move top Set/Kurta SKUs to Amazon fulfilment (FBA), which cancels less.
# 2. **Investigate the April→June decline** — check stock-outs, pricing and ad spend for the top categories.
# 3. **Focus marketing on the top 5 states**, and test campaigns in fast-growing mid-size states.
# 4. **GST:** keep most products priced ≤ ₹1,000 per piece to stay in the 5% slab; because most GST is IGST, keep inter-state invoices and GSTR-1 state-wise data clean.

# %%
# Save the clean data used by SQL / Excel / dashboard
df.to_csv(ROOT / "data" / "processed" / "sales_clean.csv.gz", index=False, compression="gzip")
print("saved")
