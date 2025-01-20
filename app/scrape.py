import time
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from urllib.parse import urlparse
from datetime import datetime
from db import Row, get_pdf, store_pdf, PDF_TTL

BASE_URL = "https://www.gov.nl.ca/dgsnl/inspections/public-alpha/"


def get_client() -> httpx.Client:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    return httpx.Client(headers=headers, follow_redirects=True)


def get_page_url(page_number: int) -> str:
    return f"{BASE_URL}page/{page_number}/"


def get_number_of_pages(client: httpx.Client) -> int:
    response = client.get(BASE_URL)
    soup = BeautifulSoup(response.text, "html.parser")

    page_numbers = soup.find_all("a", class_="page-numbers")

    if not page_numbers:
        return 1

    page_nums = [int(page.text) for page in page_numbers if page.text.isdigit()]

    return max(page_nums) if page_nums else 1


def get_page_data(client: httpx.Client, page_number: int):
    url = get_page_url(page_number)
    response = client.get(url)

    logger.info(f"Scraping page {page_number} from {url}")

    soup = BeautifulSoup(response.text, "html.parser")

    entry_content = soup.find("div", class_="entry-content")

    table = entry_content.find("table")

    rows: list[Row] = []
    for i, row in enumerate(table.find_all("tr")):
        if i == 0:
            continue

        cells = []
        for i, cell in enumerate(row.find_all(["td", "th"])):
            if i == 0:
                a_tag = cell.find("a")

                if a_tag:
                    cells.append(a_tag.get("href"))
                else:
                    raise ValueError(f"No a tag found in cell {cell}")

            text = cell.text.strip()
            text = text.split("\t")[0]
            cells.append(text)

        if len(cells) != 4:
            logger.debug(f"Problematic row: {row}, {cells}")
            raise ValueError(f"Expected 4 cells, got {len(cells)}")

        [pdf_url, name, location, region] = cells

        try:
            result = urlparse(pdf_url)
            if not all([result.scheme, result.netloc]):
                raise ValueError(f"Invalid PDF URL: {pdf_url}")
        except Exception:
            raise ValueError(f"Invalid PDF URL: {pdf_url}")

        if cells:
            rows.append(
                Row(
                    pdf_url=pdf_url,
                    name=name,
                    location=location,
                    region=region,
                )
            )
    rows = rows[1:]

    logger.info(f"Found {len(rows)} rows on page {page_number}")

    return rows


def download_pdf(client: httpx.Client, row: Row) -> Row:
    response = client.get(row.pdf_url)

    row.pdf = response.content
    row.time_since_scraped = datetime.now()

    return row


def get_populated_row(client: httpx.Client, row: Row) -> tuple[Row, bool]:
    populated_row = get_pdf(row)

    if (
        populated_row is None
        or populated_row.time_since_scraped < datetime.now() - PDF_TTL
    ):
        populated_row = download_pdf(client, populated_row or row)
        store_pdf(populated_row)
        return populated_row, True

    return populated_row, False


def scrape_page(client: httpx.Client, page_number: int) -> list[Row]:
    page_data = get_page_data(client, page_number)

    logger.info(f"Scraping page {page_number} with {len(page_data)} rows")

    for row in page_data:
        populated_row, is_new = get_populated_row(client, row)

        logger.info(f"Scraped {populated_row.name} from {populated_row.pdf_url}")

        if is_new:
            time.sleep(2)
        else:
            logger.info("Already scraped")


if __name__ == "__main__":
    client = get_client()

    number_of_pages = get_number_of_pages(client)

    logger.info(f"Found {number_of_pages} pages")

    for page_number in range(1, number_of_pages + 1):
        scrape_page(client, page_number)
