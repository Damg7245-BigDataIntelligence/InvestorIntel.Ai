from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

def get_recent_updates():
    # ─── 1. Configure headless Chrome for remote use ─────────────────────────────
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')

    # ─── 2. Connect to your standalone-chrome service ───────────────────────────
    print("🔗 Connecting to Selenium at http://selenium:4444/wd/hub")
    driver = webdriver.Remote(
        command_executor='http://selenium:4444/wd/hub',
        options=options
    )
    print("✅ Connected!")

    try:
        # ─── 3. Navigate & wait for your cards to appear ───────────────────────────
        driver.get("https://example.com/your‑updates‑page")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.recent-card-maping"))
        )

        # ─── 4. Parse the loaded HTML ───────────────────────────────────────────────
        soup = BeautifulSoup(driver.page_source, "html.parser")
        return parse_card_data(soup)

    finally:
        driver.quit()
        print("🛑 Driver shut down")

def parse_card_data(soup):
    results = []
    for div in soup.select("div.recent-card-maping"):
        spans = div.select("span")
        results.append({
            "company":  div.select_one("h4 a").get_text(strip=True),
            "funding":  spans[0].get_text(strip=True).replace("Funding ", ""),
            "valuation":spans[1].get_text(strip=True).replace("Valuation: ", ""),
            "revenue":  spans[2].get_text(strip=True).replace("Revenue ", ""),
            "growth":   spans[3].get_text(strip=True).replace("Growth ", "")
        })
    return results
