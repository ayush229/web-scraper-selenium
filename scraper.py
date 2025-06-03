# scraper.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin, urlparse
import logging
import traceback
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def initialize_driver():
    """Initializes and returns a headless Chrome WebDriver."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--incognito")

    options.binary_location = "/usr/bin/chromium-browser"

    service = None
    driver = None
    try:
        # Directly use the installed ChromeDriver binary path
        # The Dockerfile sets CHROMEDRIVER_PATH to /usr/bin/chromedriver
        chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', "/usr/bin/chromedriver") # <-- Changed this line
        
        if not os.path.exists(chromedriver_path):
            raise RuntimeError(f"ChromeDriver not found at {chromedriver_path}. Check Dockerfile installation.")
        if not os.access(chromedriver_path, os.X_OK):
            raise RuntimeError(f"ChromeDriver at {chromedriver_path} is not executable. Check Dockerfile permissions.")

        service = Service(executable_path=chromedriver_path)
        
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("Selenium WebDriver initialized successfully.")
        return driver
    except Exception as e:
        error_message = f"Failed to initialize web driver: {e}\n{traceback.format_exc()}"
        logger.error(error_message)
        if service:
            try:
                service.stop()
            except Exception as se:
                logger.error(f"Error stopping service during driver init failure: {se}")
        if driver:
            try:
                driver.quit()
            except Exception as de:
                logger.error(f"Error quitting driver during driver init failure: {de}")
        raise RuntimeError(error_message)

def scrape_website(url, type="beautify"):
    driver = None
    try:
        driver = initialize_driver()
        driver.get(url)
        logger.info(f"Successfully loaded {url}")

        if type == "raw":
            return {
                "status": "success",
                "url": url,
                "type": "raw",
                "data": driver.page_source
            }

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        content = []
        sections = soup.find_all(['section', 'div', 'article', 'main'])

        if not sections:
            body_content = soup.find('body')
            if body_content:
                sections = [body_content]
            else:
                sections = [soup]

        for sec in sections:
            section_data = {
                "heading": None,
                "content": [],
                "images": [],
                "links": []
            }

            heading = sec.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if heading:
                section_data["heading"] = {"tag": heading.name, "text": heading.get_text(strip=True)}

            paragraphs_and_lists = sec.find_all(['p', 'li', 'span'])
            for elem in paragraphs_and_lists:
                text = elem.get_text(strip=True)
                if text:
                    section_data["content"].append(text)

            for img in sec.find_all("img"):
                src = img.get("src")
                if src:
                    abs_url = urljoin(url, src)
                    section_data["images"].append(abs_url)

            for a in sec.find_all("a"):
                href = a.get("href")
                if href:
                    abs_url = urljoin(url, href.split('#')[0])
                    section_data["links"].append(abs_url)

            if section_data["heading"] or section_data["content"] or section_data["images"] or section_data["links"]:
                content.append(section_data)

        return {
            "status": "success",
            "url": url,
            "type": "beautify",
            "data": {
                "sections": content
            }
        }
    except Exception as e:
        error_message = f"Error scraping {url}: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_message)
        return {"status": "error", "error": error_message}
    finally:
        if driver:
            driver.quit()

def crawl_website(base_url, type="beautify", max_pages=50):
    visited = set()
    to_visit = [base_url.rstrip('/')]
    domain = urlparse(base_url).netloc
    all_data = []
    driver = None
    pages_processed = 0

    try:
        driver = initialize_driver()

        while to_visit and pages_processed < max_pages:
            current_url = to_visit.pop(0)
            if current_url in visited:
                continue

            logger.info(f"Crawling: {current_url}")
            visited.add(current_url)
            pages_processed += 1

            try:
                driver.get(current_url)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(driver.page_source, 'html.parser')

                result_data = None
                if type == "raw":
                    result_data = soup.prettify()
                else:
                    content_sections = []
                    main_sections = soup.find_all(['section', 'div', 'article', 'main'])
                    if not main_sections: main_sections = [soup.find('body') or soup]

                    for sec in main_sections:
                        section_data = {
                            "heading": None,
                            "content": [],
                            "images": [],
                            "links": []
                        }
                        heading = sec.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                        if heading:
                            section_data["heading"] = {"tag": heading.name, "text": heading.get_text(strip=True)}
                        for p in sec.find_all(['p', 'li', 'span']):
                            text = p.get_text(strip=True)
                            if text: section_data["content"].append(text)
                        for img in sec.find_all("img"):
                            src = img.get("src")
                            if src: section_data["images"].append(urljoin(current_url, src))
                        for a in sec.find_all("a"):
                            href = a.get("href")
                            if href: section_data["links"].append(urljoin(current_url, href.split('#')[0]))

                        if section_data["heading"] or section_data["content"] or section_data["images"] or section_data["links"]:
                            content_sections.append(section_data)

                    result_data = {"sections": content_sections}

                page_data = {"url": current_url}
                if type == "raw":
                    page_data["raw_data"] = result_data
                else:
                    page_data["content"] = result_data.get("sections", []) if isinstance(result_data, dict) else []

                all_data.append(page_data)

                if type == "beautify":
                    from selenium.webdriver.common.by import By
                    links_on_page = [elem.get_attribute('href') for elem in driver.find_elements(by=By.TAG_NAME, value='a')]
                    for link in links_on_page:
                        if link:
                            try:
                                parsed_link = urlparse(link)
                                absolute_link = urljoin(current_url, link)
                                parsed_absolute = urlparse(absolute_link)

                                if parsed_absolute.scheme in ['http', 'https'] and parsed_absolute.netloc == domain:
                                    clean_link = absolute_link.split('#')[0].rstrip('/')
                                    if clean_link not in visited and clean_link not in to_visit:
                                        logger.debug(f"Adding link to visit queue: {clean_link}")
                                        to_visit.append(clean_link)
                            except Exception as link_e:
                                logger.warning(f"Could not process link '{link}' on page {current_url}: {link_e}")

            except Exception as e:
                error_message = f"Error processing {current_url} during crawl: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_message)
                all_data.append({"url": current_url, "error": error_message})

        if pages_processed >= max_pages:
            logger.warning(f"Crawl limit ({max_pages} pages) reached for {base_url}.")

        return {
            "status": "success",
            "url": base_url,
            "type": f"crawl_{type}",
            "data": all_data
        }
    except Exception as e:
        error_message = f"Crawl failed for {base_url}: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_message)
        return {"status": "error", "error": error_message}
    finally:
        if driver:
            driver.quit()
