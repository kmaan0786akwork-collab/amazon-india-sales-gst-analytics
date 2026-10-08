"""
Cleaning + GST enrichment for the Amazon India apparel sales report (Mar–Jun 2022).

Run from the repo root:
    python src/clean_data.py
Writes data/processed/sales_clean.csv.gz
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "amazon_sale_report.csv.gz"
OUT = ROOT / "data" / "processed" / "sales_clean.csv.gz"

# ---------------------------------------------------------------------------
# Assumptions (documented in README)
# ---------------------------------------------------------------------------
# 1. "Amount" is the GST-inclusive price the customer paid (marketplace prices in India include GST).
# 2. Apparel GST slabs in force during 2022 (HSN 61/62): 5% if the sale value per piece is
#    <= Rs 1,000, otherwise 12%.
# 3. The seller's GST registration state is not in the data. We assume the seller ships from
#    SELLER_STATE. Orders shipped inside that state attract CGST + SGST (half each);
#    orders to any other state attract IGST. Change SELLER_STATE to re-run the split.
SELLER_STATE = "MAHARASHTRA"
GST_THRESHOLD_PER_PIECE = 1000
GST_LOW, GST_HIGH = 0.05, 0.12

# Typos / abbreviations found in ship-state during profiling
STATE_FIXES = {
    "NEW DELHI": "DELHI",
    "RAJSHTHAN": "RAJASTHAN", "RAJSTHAN": "RAJASTHAN", "RJ": "RAJASTHAN",
    "ORISSA": "ODISHA",
    "PONDICHERRY": "PUDUCHERRY",
    "NL": "NAGALAND",
    "PB": "PUNJAB", "PUNJAB/MOHALI/ZIRAKPUR": "PUNJAB",
    "AR": "ARUNACHAL PRADESH",
    "DADRA AND NAGAR": "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "APO": "UNKNOWN",
}

# Old / alternate city names merged into one spelling
CITY_FIXES = {
    "Bangalore": "Bengaluru", "Gurgaon": "Gurugram", "Mysore": "Mysuru", "Calcutta": "Kolkata",
    "Trivandrum": "Thiruvananthapuram", "Vizag": "Visakhapatnam", "Pondicherry": "Puducherry",
    "Mangalore": "Mangaluru",
}

# Collapse 13 raw statuses into 5 business groups
def status_group(s: str) -> str:
    if s == "Cancelled":
        return "Cancelled"
    if s in ("Shipped - Returned to Seller", "Shipped - Returning to Seller", "Shipped - Rejected by Buyer"):
        return "Returned"
    if s in ("Shipped - Lost in Transit", "Shipped - Damaged"):
        return "Lost/Damaged"
    if s.startswith("Pending") or s == "Shipping":
        return "Pending"
    return "Shipped/Delivered"


def load_raw(path: Path = RAW) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip()

    # Drop helper / empty columns, keep a simple promotion flag instead of the long promo text
    df["has_promotion"] = df["promotion-ids"].notna()
    df = df.drop(columns=["index", "Unnamed: 22", "promotion-ids", "currency", "ship-country", "fulfilled-by"])

    # Exact duplicate rows
    df = df.drop_duplicates()

    df = df.rename(columns={
        "Order ID": "order_id", "Date": "order_date", "Status": "status", "Fulfilment": "fulfilment",
        "Sales Channel": "sales_channel", "ship-service-level": "service_level", "Style": "style",
        "SKU": "sku", "Category": "category", "Size": "size", "ASIN": "asin",
        "Courier Status": "courier_status", "Qty": "qty", "Amount": "amount",
        "ship-city": "ship_city", "ship-state": "ship_state", "ship-postal-code": "ship_postal_code",
        "B2B": "is_b2b",
    })

    df["order_date"] = pd.to_datetime(df["order_date"], format="%m-%d-%y")
    df["order_month"] = df["order_date"].dt.to_period("M").astype(str)
    df["category"] = df["category"].str.strip().str.title()

    # Location cleanup
    df["ship_state"] = df["ship_state"].str.strip().str.upper().replace(STATE_FIXES).fillna("UNKNOWN")
    df["ship_city"] = df["ship_city"].str.strip().str.title().replace(CITY_FIXES).fillna("Unknown")
    df["courier_status"] = df["courier_status"].fillna("Not Available")

    df["status_group"] = df["status"].map(status_group)

    # Revenue that actually stays with the seller: shipped / delivered orders with qty >= 1
    df["amount"] = df["amount"].fillna(0.0)
    df["is_net_sale"] = (df["status_group"] == "Shipped/Delivered") & (df["qty"] > 0) & (df["amount"] > 0)

    # ---------------- GST enrichment ----------------
    per_piece = df["amount"] / df["qty"].where(df["qty"] > 0)
    df["gst_rate"] = per_piece.le(GST_THRESHOLD_PER_PIECE).map({True: GST_LOW, False: GST_HIGH})
    df.loc[per_piece.isna(), "gst_rate"] = GST_LOW
    df["taxable_value"] = (df["amount"] / (1 + df["gst_rate"])).round(2)
    df["gst_amount"] = (df["amount"] - df["taxable_value"]).round(2)
    intra = df["ship_state"].eq(SELLER_STATE)
    df["supply_type"] = intra.map({True: "Intra-state", False: "Inter-state"})
    df["cgst"] = (df["gst_amount"] / 2).where(intra, 0).round(2)
    df["sgst"] = df["cgst"]
    df["igst"] = df["gst_amount"].where(~intra, 0).round(2)
    return df


if __name__ == "__main__":
    raw = load_raw()
    clean_df = clean(raw)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(OUT, index=False, compression="gzip")
    print(f"raw rows: {len(raw):,} -> clean rows: {len(clean_df):,}  ->  {OUT.relative_to(ROOT)}")
