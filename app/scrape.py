import httpx
from bs4 import BeautifulSoup

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
    soup = BeautifulSoup(response.text, "html.parser")

    entry_content = soup.find("div", class_="entry-content")

    table = entry_content.find("table")

    rows = []
    for row in table.find_all("tr"):
        cells = []
        for i, cell in enumerate(row.find_all(["td", "th"])):
            if i == 0:
                a_tag = cell.find("a")

                if a_tag:
                    cells.append(a_tag.get("href"))

            text = cell.text.strip()
            text = text.split("\t")[0]
            cells.append(text)

        if cells:
            rows.append(cells)

    rows = rows[1:]

    return rows


if __name__ == "__main__":
    import tempfile
    import pdfplumber
    from process_pdfs import process_page

    client = get_client()
    print(get_number_of_pages(client))

    page_data = get_page_data(client, 1)

    for row in page_data:
        print(row)

    if page_data:
        pdf_url = page_data[1][0]
        pdf_response = client.get(pdf_url)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(pdf_response.content)
            tmp_file.flush()

            with pdfplumber.open(tmp_file.name) as pdf:
                for page in pdf.pages:
                    all_lines, records = process_page(page)
                    for record in records:
                        print(record)
