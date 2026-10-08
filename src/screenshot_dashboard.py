"""
Saves a preview image of the dashboard to images/00_dashboard.png (used in the README).

    pip install playwright && playwright install chromium
    python src/screenshot_dashboard.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 1080}, device_scale_factor=1.5)
    page.goto((ROOT / "docs" / "index.html").as_uri())
    page.wait_for_timeout(2500)
    page.screenshot(path=str(ROOT / "images" / "00_dashboard.png"), clip={"x": 0, "y": 0, "width": 1280, "height": 1080})
    browser.close()
print("saved images/00_dashboard.png")
