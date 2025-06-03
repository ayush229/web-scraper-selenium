# scraper.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urljoin, urlparse
import logging
import traceback # Import traceback for detailed error logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def initialize_driver():
    """Initializes and returns a headless Chrome WebDriver."""
    options = Options()
    options.add_argument("--headless")  # Run Chrome in headless mode (no UI)
    options.add_argument("--no-sandbox")  # Required for running in Docker/Railway
    options.add_argument("--disable-dev-shm-usage")  # Overcomes resource limitations
    options.add_argument("--disable-gpu") # Applicable to older versions of Chrome
    options.add_argument("--window-size=1920,1080") # Set a default window size
    options.add_argument("--start-maximized")
    options.add_argument("--incognito") # Browse in incognito mode

    # Path to Chromium executable if not in default PATH (e.g., in Docker)
    # The Dockerfile sets CHROME_BIN, which ChromeDriverManager might pick up,
    # but explicitly setting it via binary_location can sometimes help.
    # If you install chromium-browser, the binary is typically at /usr/bin/chromium-browser
    options.binary_location = "/usr/bin/chromium-browser" # Or /usr/bin/google-chrome

    service = None
    driver = None
    try:
        # Use ChromeDriverManager to automatically download and manage ChromeDriver
        # This is useful for local development and can work in Docker if the binary location is specified.
        # Ensure that the PATH in your Dockerfile includes /usr/bin for chromium-driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("Selenium WebDriver initialized successfully.")
        return driver
    except Exception as e:
        error_message = f"Failed to initialize web driver: {e}\n{traceback.format_exc()}"
        logger.error(error_message)
        # Attempt to close the service/driver if they were partially initialized
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
        raise RuntimeError(error_message) # Re-raise as a RuntimeError to be caught upstream

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
            - "data": The extracted data. If type is "raw", this is the raw HTML.
                      If type is "beautify", this is a structured dictionary.
            - "error": (Only present if status is "error") A string describing the error.
    """
    driver = None
    try:
        driver = initialize_driver()
        driver.get(url)
        logger.info(f"Successfully loaded {url}")

        # Wait for some content to load if needed (e.g., using WebDriverWait)
        # For simplicity, we'll proceed directly to get page source

        if type == "raw":
            return {
                "status": "success",
                "url": url,
                "type": "raw",
                "data": driver.page_source # Get the full rendered HTML
            }

        # For "beautify" type, parse the rendered HTML with BeautifulSoup
        from bs4 import BeautifulSoup # Import BeautifulSoup here as it's only needed for beautify
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        content = []
        # Find major content sections; adjust selectors based on typical website structures
        sections = soup.find_all(['section', 'div', 'article', 'main'])

        # If no specific sections found, consider the whole body or main content area
        if not sections:
            body_content = soup.find('body')
            if body_content:
                sections = [body_content]
            else:
                sections = [soup] # Fallback to the whole document

        for sec in sections:
            section_data = {
                "heading": None,
                "content": [],
                "images": [],
                "links": []
            }

            # Find the most prominent heading within the section
            heading = sec.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if heading:
                section_data["heading"] = {"tag": heading.name, "text": heading.get_text(strip=True)}

            # Find paragraphs and list items for general content
            paragraphs_and_lists = sec.find_all(['p', 'li', 'span']) # Added span as it's often used for text
            for elem in paragraphs_and_lists:
                text = elem.get_text(strip=True)
                if text:
                    section_data["content"].append(text)

            # Extract image URLs
            for img in sec.find_all("img"):
                src = img.get("src")
                if src:
                    abs_url = urljoin(url, src)
                    section_data["images"].append(abs_url)

            # Extract links
            for a in sec.find_all("a"):
                href = a.get("href")
                if href:
                    abs_url = urljoin(url, href.split('#')[0]) # Remove fragment identifiers
                    section_data["links"].append(abs_url)

            # Only include sections with data
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
            driver.quit() # Ensure the browser is closed after each scrape

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
    to_visit = [base_url.rstrip('/')] # Normalize base URL
    domain = urlparse(base_url).netloc
    all_data = []
    driver = None # Initialize driver outside the loop to reuse it
    pages_processed = 0

    try:
        driver = initialize_driver() # Initialize driver once for the crawl session

        while to_visit and pages_processed < max_pages:
            current_url = to_visit.pop(0)
            if current_url in visited:
                continue

            logger.info(f"Crawling: {current_url}")
            visited.add(current_url)
            pages_processed += 1

            try:
                driver.get(current_url)
                # For beautify, parse the page source with BeautifulSoup
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(driver.page_source, 'html.parser')

                result_data = None
                if type == "raw":
                    result_data = soup.prettify()
                else: # beautify
                    content_sections = []
                    main_sections = soup.find_all(['section', 'div', 'article', 'main'])
                    if not main_sections: main_sections = [soup.find('body') or soup] # Fallback

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

                # Extract links for crawling (only for beautify mode, as raw doesn't need to crawl)
                if type == "beautify":
                    # Get all links from the current page's HTML using Selenium directly
                    # This is often more reliable for dynamic links than parsing static soup
                    links_on_page = [elem.get_attribute('href') for elem in driver.find_elements(by=webdriver.common.by.By.TAG_NAME, value='a')]
                    for link in links_on_page:
                        if link:
                            try:
                                parsed_link = urlparse(link)
                                absolute_link = urljoin(current_url, link)
                                parsed_absolute = urlparse(absolute_link)

                                # Check if the link is within the same domain and is http/https
                                if parsed_absolute.scheme in ['http', 'https'] and parsed_absolute.netloc == domain:
                                    clean_link = absolute_link.split('#')[0].rstrip('/') # Remove fragment and trailing slash
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
            driver.quit() # Ensure the browser is closed after the crawl session
