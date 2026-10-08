"""
Builds the interactive dashboard at docs/index.html (served by GitHub Pages).

    python src/build_dashboard.py
"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(ROOT / "data" / "processed" / "sales_clean.csv.gz", parse_dates=["order_date"])
df["slab"] = (df.gst_rate * 100).round().astype(int)

# Pre-aggregated cube (keeps the page light; the browser filters and sums it)
cube = (df.groupby(["order_month", "category", "ship_state", "status_group", "fulfilment", "slab", "is_net_sale"])
          .agg(lines=("order_id", "size"), qty=("qty", "sum"), amount=("amount", "sum"),
               gst=("gst_amount", "sum"), cgst=("cgst", "sum"), sgst=("sgst", "sum"), igst=("igst", "sum"))
          .reset_index())
cube[["amount", "gst", "cgst", "sgst", "igst"]] = cube[["amount", "gst", "cgst", "sgst", "igst"]].round(2)
cube["is_net_sale"] = cube["is_net_sale"].astype(int)

trend = df[df.is_net_sale & df.order_date.between("2022-04-01", "2022-06-28")]
daily = (trend.groupby([trend.order_date.dt.strftime("%Y-%m-%d"), "category"]).amount.sum().round(2)
              .reset_index().rename(columns={"order_date": "d"}))

data = {
    "cols": list(cube.columns), "rows": cube.values.tolist(),
    "daily": daily.values.tolist(),
    "months": sorted(df.order_month.unique().tolist()),
    "categories": df[df.is_net_sale].groupby("category").amount.sum().sort_values(ascending=False).index.tolist(),
}

template = (ROOT / "src" / "dashboard_template.html").read_text(encoding="utf-8")
html = template.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "index.html").write_text(html, encoding="utf-8")
print(f"docs/index.html written ({len(html)/1024:,.0f} KB, {len(cube):,} cube rows)")
