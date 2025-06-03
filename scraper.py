# scraper.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin, urlparse
import logging
import time

# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def initialize_driver():
    """Initializes a headless Chrome WebDriver."""
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")  # Suppress excessive logging
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logger.error(f"Error initializing Chrome driver: {e}")
        return None

def scrape_website(url, type="beautify"):
    """
    Scrapes a website using Selenium and extracts content.

    Args:
        url (str): The URL of the website to scrape.
        type (str, optional): The type of content to extract. Defaults to "beautify".
            Valid values are "raw" and "beautify".

    Returns:
        dict: A dictionary containing the status of the scraping operation and the extracted data.
            - "status": "success" or "error"
            - "url": The URL of the website.
            - "type": The type of content extracted.
            - "data": The extracted data. If type is "raw", this is the page source HTML.
                      If type is "beautify", this is a structured dictionary.
            - "error": (Only present if status is "error") A string describing the error.
    """
    driver = initialize_driver()
    if not driver:
        return {"status": "error", "error": "Failed to initialize web driver."}

    try:
        logger.info(f"Navigating to {url} with Selenium.")
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        # Give a little extra time for dynamic content to load, if necessary
        time.sleep(2)

        if type == "raw":
            return {
                "status": "success",
                "url": url,
                "type": "raw",
                "data": driver.page_source
            }

        # For "beautify" type, extract structured content
        content = []
        # Find common content-holding elements. Adjust these selectors as needed for target sites.
        elements = driver.find_elements(By.XPATH, "//body//h1 | //body//h2 | //body//h3 | //body//h4 | //body//h5 | //body//h6 | //body//p | //body//li | //body//img | //body//a")

        current_section_data = {
            "heading": None,
            "content": [],
            "images": [],
            "links": []
        }

        for element in elements:
            tag_name = element.tag_name

            if tag_name.startswith('h'):
                if current_section_data["content"] or current_section_data["images"] or current_section_data["links"]:
                    # If current_section_data has content, it means a new heading starts a new section
                    content.append(current_section_data)
                    current_section_data = {
                        "heading": None,
                        "content": [],
                        "images": [],
                        "links": []
                    }
                current_section_data["heading"] = {"tag": element.tag_name, "text": element.text.strip()}
            elif tag_name == 'p' or tag_name == 'li':
                text = element.text.strip()
                if text:
                    current_section_data["content"].append(text)
            elif tag_name == 'img':
                src = element.get_attribute("src")
                if src:
                    abs_url = urljoin(url, src)
                    current_section_data["images"].append(abs_url)
            elif tag_name == 'a':
                href = element.get_attribute("href")
                if href:
                    abs_url = urljoin(url, href.split('#')[0])
                    current_section_data["links"].append(abs_url)

        # Add the last accumulated section if it has content
        if current_section_data["heading"] or current_section_data["content"] or current_section_data["images"] or current_section_data["links"]:
            content.append(current_section_data)

        return {
            "status": "success",
            "url": url,
            "type": "beautify",
            "data": {
                "sections": content
            }
        }
    except Exception as e:
        error_message = f"Error scraping {url} with Selenium: {str(e)}"
        logger.error(error_message)
        return {"status": "error", "error": error_message}
    finally:
        if driver:
            driver.quit()


def crawl_website(base_url, type="beautify", max_pages=50):
    """
    Crawls a website using Selenium, starting from a base URL, and extracts content from multiple pages.

    Args:
        base_url (str): The starting URL for the crawl.
        type (str, optional): The type of content to extract. Defaults to "beautify".
            Valid values are "raw" and "beautify".
        max_pages (int, optional): The maximum number of pages to crawl. Defaults to 50.

    Returns:
        dict: A dictionary containing the status of the crawl and the extracted data.
            - "status": "success" or "error"
            - "url": The base URL of the crawl.
            - "type": The type of content extracted.
            - "data": A list of dictionaries, where each dictionary represents the data from a crawled page.
                      Each page dictionary contains:
                        - "url": The URL of the page.
                        - "raw_data": (If type is "raw") The raw HTML of the page.
                        - "content": (If type is "beautify") A list of structured content sections.
            - "error": (Only present if status is "error") A string describing the error.
    """
    visited = set()
    to_visit = [base_url]
    domain = urlparse(base_url).netloc
    all_data = []
    driver = initialize_driver() # Initialize driver once for the crawl
    if not driver:
        return {"status": "error", "error": "Failed to initialize web driver for crawl."}

    try:
        while to_visit and len(visited) < max_pages:
            current_url = to_visit.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            try:
                logger.info(f"Crawling (Selenium): {current_url}")
                driver.get(current_url)
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(2) # Allow for dynamic content

                page_data = {"url": current_url}
                if type == "raw":
                    page_data["raw_data"] = driver.page_source
                else: # beautify
                    page_content_sections = []
                    elements = driver.find_elements(By.XPATH, "//body//h1 | //body//h2 | //body//h3 | //body//h4 | //body//h5 | //body//h6 | //body//p | //body//li | //body//img | //body//a")

                    current_section_data = {
                        "heading": None,
                        "content": [],
                        "images": [],
                        "links": []
                    }

                    for element in elements:
                        tag_name = element.tag_name
                        if tag_name.startswith('h'):
                            if current_section_data["content"] or current_section_data["images"] or current_section_data["links"]:
                                page_content_sections.append(current_section_data)
                                current_section_data = {
                                    "heading": None,
                                    "content": [],
                                    "images": [],
                                    "links": []
                                }
                            current_section_data["heading"] = {"tag": element.tag_name, "text": element.text.strip()}
                        elif tag_name == 'p' or tag_name == 'li':
                            text = element.text.strip()
                            if text:
                                current_section_data["content"].append(text)
                        elif tag_name == 'img':
                            src = element.get_attribute("src")
                            if src:
                                abs_url = urljoin(current_url, src)
                                current_section_data["images"].append(abs_url)
                        elif tag_name == 'a':
                            href = element.get_attribute("href")
                            if href:
                                abs_url = urljoin(current_url, href.split('#')[0])
                                current_section_data["links"].append(abs_url)

                                parsed_link = urlparse(abs_url)
                                if parsed_link.scheme in ['http', 'https'] and parsed_link.netloc == domain:
                                    clean_link = abs_url.rstrip('/')
                                    if clean_link not in visited and clean_link not in to_visit:
                                        to_visit.append(clean_link)

                    if current_section_data["heading"] or current_section_data["content"] or current_section_data["images"] or current_section_data["links"]:
                        page_content_sections.append(current_section_data)

                    page_data["content"] = page_content_sections

                all_data.append(page_data)

            except Exception as e:
                error_message = f"Error processing {current_url} during crawl with Selenium: {e}"
                logger.error(error_message)
                all_data.append({"url": current_url, "error": error_message})

        return {
            "status": "success",
            "url": base_url,
            "type": f"crawl_{type}",
            "data": all_data
        }
    except Exception as e:
        error_message = f"Crawl failed for {base_url} with Selenium: {e}"
        logger.error(error_message)
        return {"status": "error", "error": error_message}
    finally:
        if driver:
            driver.quit()
