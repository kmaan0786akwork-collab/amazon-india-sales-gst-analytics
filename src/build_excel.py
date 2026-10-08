"""
Builds excel/Sales_GST_Report.xlsx — a formula-driven GST report (SUMIFS, INDEX/MATCH, IF).

    python src/build_excel.py
"""
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(ROOT / "data" / "processed" / "sales_clean.csv.gz")
net = df[df.is_net_sale].copy()
net["per_piece"] = (net.amount / net.qty).round(2)
net = net.sort_values(["order_date", "order_id"])

F = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3A5F")
HDR_FONT = Font(name=F, bold=True, color="FFFFFF")
INPUT_FONT = Font(name=F, color="0000FF", bold=True)
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
BASE = Font(name=F)
BOLD = Font(name=F, bold=True)
TITLE = Font(name=F, bold=True, size=14, color="1F3A5F")
NOTE = Font(name=F, italic=True, size=9, color="595959")
thin = Side(style="thin", color="D9D9D9")
BOX = Border(top=thin, bottom=thin, left=thin, right=thin)
INR = '₹#,##0;-₹#,##0'
PCT = '0.0%'

wb = Workbook()

def header(ws, row, cols):
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font, cell.fill = HDR_FONT, HDR_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 30

def widths(ws, w):
    for i, x in enumerate(w, 1):
        ws.column_dimensions[get_column_letter(i)].width = x

# ---------------- Assumptions ----------------
A = wb.active; A.title = "Assumptions"
A["A1"] = "GST assumptions (edit the yellow cells — every sheet recalculates)"; A["A1"].font = TITLE
rows = [
    ("GST threshold per piece (₹)", 1000, "Apparel (HSN 61/62) in 2022: 5% if sale value per piece ≤ ₹1,000, else 12%"),
    ("GST rate – at or below threshold", 0.05, "Lower apparel slab"),
    ("GST rate – above threshold", 0.12, "Higher apparel slab"),
    ("Seller GST registration state", "MAHARASHTRA", "Not in the data — assumed. Same state = CGST+SGST, other states = IGST"),
]
header(A, 3, ["Input", "Value", "Note"])
for r, (k, v, n) in enumerate(rows, 4):
    A.cell(row=r, column=1, value=k).font = BASE
    c = A.cell(row=r, column=2, value=v); c.font, c.fill, c.border = INPUT_FONT, INPUT_FILL, BOX
    A.cell(row=r, column=3, value=n).font = NOTE
A["B5"].number_format = A["B6"].number_format = '0%'
A["B4"].number_format = INR
A["A10"] = "Amounts in the data are treated as GST-inclusive prices. Taxable value = Amount ÷ (1 + rate)."; A["A10"].font = NOTE
A["A11"] = "Source data: Amazon Sale Report (Amazon India apparel orders, 31 Mar – 29 Jun 2022), public Kaggle dataset."; A["A11"].font = NOTE
widths(A, [36, 16, 80])
THR, LOW, HIGH, SELLER = "Assumptions!$B$4", "Assumptions!$B$5", "Assumptions!$B$6", "Assumptions!$B$7"

# ---------------- Sales_Data ----------------
D = wb.create_sheet("Sales_Data")
cols = ["Order ID", "Order Date", "Month", "Category", "Ship State", "Qty", "Amount (₹, GST incl.)", "Price per Piece (₹)", "Fulfilment", "B2B"]
header(D, 1, cols)
for r in net[["order_id", "order_date", "order_month", "category", "ship_state", "qty", "amount", "per_piece", "fulfilment", "is_b2b"]].itertuples(index=False):
    D.append([r[0], pd.Timestamp(r[1]).to_pydatetime().date(), r[2], r[3], r[4], int(r[5]), float(r[6]), float(r[7]), r[8], "Yes" if r[9] else "No"])
N = len(net) + 1
for row in D.iter_rows(min_row=2, max_row=N):
    row[1].number_format = "dd-mmm-yy"; row[6].number_format = INR; row[7].number_format = INR
widths(D, [22, 12, 10, 15, 26, 6, 18, 16, 11, 6])
D.freeze_panes = "A2"; D.auto_filter.ref = f"A1:J{N}"
rng = lambda col: f"Sales_Data!${col}$2:${col}${N}"
AMT, PP, ST, MO, CAT, QTY = rng("G"), rng("H"), rng("E"), rng("C"), rng("D"), rng("F")

def gst_block(ws, r, key_rng, key_cell):
    """Columns B..K for one row: sales, low-slab sales, high-slab sales, taxable, gst, supply, cgst, sgst, igst."""
    ws[f"B{r}"] = f"=SUMIFS({AMT},{key_rng},{key_cell})"
    ws[f"C{r}"] = f'=SUMIFS({AMT},{key_rng},{key_cell},{PP},"<="&{THR})'
    ws[f"D{r}"] = f"=B{r}-C{r}"
    ws[f"E{r}"] = f"=C{r}/(1+{LOW})+D{r}/(1+{HIGH})"
    ws[f"F{r}"] = f"=B{r}-E{r}"

# ---------------- State_GST ----------------
S = wb.create_sheet("State_GST")
S["A1"] = "State-wise sales & GST (net sales only)"; S["A1"].font = TITLE
header(S, 3, ["Ship State (place of supply)", "Net Sales (₹)", "Sales ≤ threshold (₹)", "Sales > threshold (₹)",
              "Taxable Value (₹)", "Total GST (₹)", "Supply Type", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Share of Sales"])
states = net.groupby("ship_state").amount.sum().sort_values(ascending=False).index.tolist()
first = 4; last = first + len(states) - 1; tot = last + 1
for i, st in enumerate(states):
    r = first + i
    S[f"A{r}"] = st
    gst_block(S, r, ST, f"$A{r}")
    S[f"G{r}"] = f'=IF($A{r}={SELLER},"Intra-state","Inter-state")'
    S[f"H{r}"] = f'=IF(G{r}="Intra-state",F{r}/2,0)'
    S[f"I{r}"] = f"=H{r}"
    S[f"J{r}"] = f'=IF(G{r}="Inter-state",F{r},0)'
    S[f"K{r}"] = f"=B{r}/$B${tot}"
S[f"A{tot}"] = "TOTAL"
for col in "BCDEFHIJ":
    S[f"{col}{tot}"] = f"=SUM({col}{first}:{col}{last})"
S[f"K{tot}"] = f"=SUM(K{first}:K{last})"
for row in S.iter_rows(min_row=first, max_row=tot, max_col=11):
    for c in row:
        c.font = BOLD if c.row == tot else BASE; c.border = BOX
        if c.column in (2, 3, 4, 5, 6, 8, 9, 10): c.number_format = INR
        if c.column == 11: c.number_format = PCT
widths(S, [34, 15, 17, 17, 16, 14, 13, 12, 12, 13, 11]); S.freeze_panes = "B4"

# ---------------- Monthly_GST ----------------
M = wb.create_sheet("Monthly_GST")
M["A1"] = "Monthly GST summary (GSTR-3B style)"; M["A1"].font = TITLE
header(M, 3, ["Month", "Net Sales (₹)", "Sales ≤ threshold (₹)", "Sales > threshold (₹)", "Taxable Value (₹)",
              "Total GST (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Orders (lines)"])
months = sorted(net.order_month.unique())
mf = 4; ml = mf + len(months) - 1; mt = ml + 1
for i, mo in enumerate(months):
    r = mf + i
    M[f"A{r}"] = mo
    gst_block(M, r, MO, f"$A{r}")
    M[f"G{r}"] = f'=SUMIFS({AMT},{MO},$A{r},{ST},{SELLER},{PP},"<="&{THR})*(1-1/(1+{LOW}))/2+SUMIFS({AMT},{MO},$A{r},{ST},{SELLER},{PP},">"&{THR})*(1-1/(1+{HIGH}))/2'
    M[f"H{r}"] = f"=G{r}"
    M[f"I{r}"] = f"=F{r}-G{r}-H{r}"
    M[f"J{r}"] = f"=COUNTIFS({MO},$A{r})"
M[f"A{mt}"] = "TOTAL"
for col in "BCDEFGHIJ":
    M[f"{col}{mt}"] = f"=SUM({col}{mf}:{col}{ml})"
for row in M.iter_rows(min_row=mf, max_row=mt, max_col=10):
    for c in row:
        c.font = BOLD if c.row == mt else BASE; c.border = BOX
        if 2 <= c.column <= 9: c.number_format = INR
        if c.column == 10: c.number_format = "#,##0"
M[f"A{mt+2}"] = "2022-03 contains a single day (31 Mar)."; M[f"A{mt+2}"].font = NOTE
widths(M, [12, 15, 17, 17, 16, 14, 12, 12, 13, 13])

# ---------------- Category ----------------
C = wb.create_sheet("Category")
C["A1"] = "Category performance (net sales)"; C["A1"].font = TITLE
header(C, 3, ["Category", "Net Sales (₹)", "Units", "Avg Price per Unit (₹)", "Share of Sales", "GST (₹)"])
cats = net.groupby("category").amount.sum().sort_values(ascending=False).index.tolist()
cf = 4; cl = cf + len(cats) - 1; ct = cl + 1
for i, ca in enumerate(cats):
    r = cf + i
    C[f"A{r}"] = ca
    C[f"B{r}"] = f"=SUMIFS({AMT},{CAT},$A{r})"
    C[f"C{r}"] = f"=SUMIFS({QTY},{CAT},$A{r})"
    C[f"D{r}"] = f"=IFERROR(B{r}/C{r},0)"
    C[f"E{r}"] = f"=B{r}/$B${ct}"
    C[f"F{r}"] = (f'=SUMIFS({AMT},{CAT},$A{r},{PP},"<="&{THR})*(1-1/(1+{LOW}))'
                  f'+SUMIFS({AMT},{CAT},$A{r},{PP},">"&{THR})*(1-1/(1+{HIGH}))')
C[f"A{ct}"] = "TOTAL"
C[f"B{ct}"] = f"=SUM(B{cf}:B{cl})"; C[f"C{ct}"] = f"=SUM(C{cf}:C{cl})"
C[f"D{ct}"] = f"=B{ct}/C{ct}"; C[f"E{ct}"] = f"=SUM(E{cf}:E{cl})"; C[f"F{ct}"] = f"=SUM(F{cf}:F{cl})"
for row in C.iter_rows(min_row=cf, max_row=ct, max_col=6):
    for c in row:
        c.font = BOLD if c.row == ct else BASE; c.border = BOX
        if c.column in (2, 4, 6): c.number_format = INR
        if c.column == 3: c.number_format = "#,##0"
        if c.column == 5: c.number_format = PCT
widths(C, [16, 15, 10, 18, 13, 13])

# ---------------- Summary (first tab) ----------------
X = wb.create_sheet("Summary", 0)
X["A1"] = "Amazon India Sales & GST Report — Apr–Jun 2022"; X["A1"].font = TITLE
X["A2"] = "Net sales = shipped/delivered order lines (cancelled, returned, pending excluded). All figures are formulas."; X["A2"].font = NOTE
header(X, 4, ["Metric", "Value"])
kpis = [
    ("Net sales (₹)", f"=SUM({AMT})", INR),
    ("Order lines (net)", f"=COUNTA({rng('A')})", "#,##0"),
    ("Units sold", f"=SUM({QTY})", "#,##0"),
    ("Avg price per unit (₹)", "=B5/B7", INR),
    ("Taxable value (₹)", f"=State_GST!E{tot}", INR),
    ("Estimated GST (₹)", f"=State_GST!F{tot}", INR),
    ("  CGST (₹)", f"=State_GST!H{tot}", INR),
    ("  SGST (₹)", f"=State_GST!I{tot}", INR),
    ("  IGST (₹)", f"=State_GST!J{tot}", INR),
    ("IGST share of GST", "=B13/B10", PCT),
    ("Sales in lower GST slab", f"=State_GST!C{tot}/State_GST!B{tot}", PCT),
    ("Top state", f"=INDEX(State_GST!A{first}:A{last},MATCH(MAX(State_GST!B{first}:B{last}),State_GST!B{first}:B{last},0))", None),
    ("Top 5 states share", f"=SUM(State_GST!K{first}:K{first+4})", PCT),
    ("Top category", f"=INDEX(Category!A{cf}:A{cl},MATCH(MAX(Category!B{cf}:B{cl}),Category!B{cf}:B{cl},0))", None),
    ("Top category share", f"=MAX(Category!E{cf}:E{cl})", PCT),
]
for i, (k, f, fmt) in enumerate(kpis, 5):
    X[f"A{i}"] = k; X[f"A{i}"].font = BASE
    X[f"B{i}"] = f; X[f"B{i}"].font = BOLD
    if fmt: X[f"B{i}"].number_format = fmt
    X[f"A{i}"].border = X[f"B{i}"].border = BOX
X["B10"].comment = Comment("Depends on the GST assumptions on the Assumptions sheet.", "Analyst")
widths(X, [30, 20])

for ws in wb.worksheets:
    ws.sheet_view.showGridLines = ws.title == "Sales_Data"
wb.calculation.fullCalcOnLoad = True  # Excel computes all formulas when the file is opened
(ROOT / "excel").mkdir(exist_ok=True)
wb.save(ROOT / "excel" / "Sales_GST_Report.xlsx")
print("rows", N - 1, "states", len(states))
