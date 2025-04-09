from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
from dotenv import load_dotenv
import os
import io

def scrape_growjo_data():

    # Load environment variables
    load_dotenv()
    GROWJO_EMAIL = os.getenv("GROWJO_EMAIL")
    GROWJO_PASSWORD = os.getenv("GROWJO_PASSWORD")
    if not GROWJO_EMAIL or not GROWJO_PASSWORD:
        raise ValueError("Please set GROWJO_EMAIL and GROWJO_PASSWORD in your .env file.")


    # Set up Selenium WebDriver options
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    #options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("--window-size=1920,1080")

    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.fonts": 2,
    }
    options.add_experimental_option("prefs", prefs)

    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    # Open the login page
    driver.get("https://growjo.com/login")

    # Wait for the input fields
    wait = WebDriverWait(driver, 10)
    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    password_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))

    # Fill in credentials
    email_input.send_keys(GROWJO_EMAIL)
    password_input.send_keys(GROWJO_PASSWORD)

    # Click the "Sign In" button using its visible text
    sign_in_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Sign In']")))
    sign_in_button.click()

    time.sleep(10)

    # Wait for the dashboard or tab area to load
    companies_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'nav-link') and text()='Companies']")))
    companies_tab.click()

    # Short wait to ensure dropdown becomes available
    time.sleep(5)

    # Click the "Select Country" dropdown
    dropdown_placeholder = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'select__placeholder') and contains(text(),'Select Country')]")))
    dropdown_placeholder.click()

    # Wait for all country options to load
    options_list = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'select__option')]")))

    # Select the first option — United States
    options_list[0].click()  # United States is first
    print("✅ Selected 'United States'")

    # Optional: sleep to observe before ending the script
    time.sleep(5)

    # Step 3: Scrape multiple pages
    all_rows = []
    headers = []
    cnt=0

    while True:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'table.cstm-table')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find('table', {'class': 'cstm-table'})

        # Get headers once
        if not headers:
            headers = [th.text.strip() for th in table.find('thead').find_all('th')]

        # Extract current page's first row rank to detect page change later
        first_rank = table.find('tbody').find('tr').find('td').text.strip()

        # Extract rows
        for tr in table.find('tbody').find_all('tr'):
            cells = tr.find_all('td')
            row = []

            for idx, cell in enumerate(cells):
                if idx == 1:
                    anchors = cell.find_all('a')
                    full_name = None
                    for a in anchors:
                        href = a.get('href')
                        if href and "/company/" in href:
                            full_name = href.split('/')[-1].replace('_', ' ')
                            break
                    row.append(full_name if full_name else cell.text.strip())
                else:
                    row.append(cell.text.strip())
            all_rows.append(row)
        
        #time.sleep(1)
        # Pagination check
        next_li = soup.find('li', class_='next')
        if next_li and next_li.find('a') and next_li.find('a').get('href'):
            try:
                next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//li[@class='next']/a[@href]")))
                driver.execute_script("arguments[0].click();", next_button)
                time.sleep(1)  # Wait for the next page to load
            except Exception as e:
                print("❌ Failed to click next or wait for new data:", e)
                break
        else:
            print("✅ Reached the last page — exiting loop.")
            break

        cnt += 1
        print(f"📄 Page {cnt + 1} scraped.")

        # if cnt == 10:
        #     print("✅ Scraped 10 pages — exiting loop.")
        #     break



    # Step 4: Save to DataFrame and CSV
    df = pd.DataFrame(all_rows, columns=headers)
    print(df)
    df.to_csv("growjo_companies_usa_all_pages.csv", index=False)

    driver.quit()    

    # Convert to CSV in-memory
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue().encode()  # convert to binary content

    return csv_content