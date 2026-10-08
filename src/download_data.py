"""
Downloads the public "Amazon Sale Report" CSV (Amazon India apparel orders, Mar–Jun 2022)
and stores it compressed at data/raw/amazon_sale_report.csv.gz

    python src/download_data.py
"""
from pathlib import Path
import gzip
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "amazon_sale_report.csv.gz"
# Public mirror of the Kaggle "E-Commerce Sales Dataset" file "Amazon Sale Report.csv"
URL = "https://raw.githubusercontent.com/babnndeep/amazon-sales-analysis/main/Amazon%20Sale%20Report.csv"

if __name__ == "__main__":
    if OUT.exists():
        print(f"already present: {OUT.relative_to(ROOT)}")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(URL, timeout=120) as r:
            data = r.read()
        with gzip.open(OUT, "wb") as f:
            f.write(data)
        print(f"downloaded {len(data)/1e6:.1f} MB -> {OUT.relative_to(ROOT)}")
