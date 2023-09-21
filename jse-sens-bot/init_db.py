import sqlite3
from bs4 import BeautifulSoup
from pathlib import Path

import urllib.request
import urllib.parse
import os
import json
import pdfplumber
from urllib.parse import urlparse, unquote
stor_pth_hist = Path(".") / Path("store") / Path("dl-history")
stor_pth_hist.mkdir(parents = True, exist_ok = True)


connection = sqlite3.connect('database.db')
# with open('schema.sql') as f:
#     connection.executescript(f.read())


html = open("..\\SENS Announcements _ JSE Client Portal.html", "r", encoding="utf-8") 
source = html.read()
print(source)

soup = BeautifulSoup(source, "lxml")
# print(soup)

sens_announcements = []
just_text_ls = []


def wdownload_file(url, fname):
    '''
    Send an collection of mapping jobs to the API in order to obtain the
    associated FIGI(s).

    Parameters
    ----------
    jobs : list(dict)
        A list of dicts that conform to the OpenFIGI API request structure. See
        https://www.openfigi.com/api#request-format for more information. Note
        rate-limiting requirements when considering length of `jobs`.

    Returns
    -------
    list(dict)
        One dict per item in `jobs` list that conform to the OpenFIGI API
        response structure.  See https://www.openfigi.com/api#response-fomats
        for more information.
    '''
    try:

        # logger.debug(f"Downloading from url: {url} to: {fname}")

        # proxies = PROXY_DICT
        handler = urllib.request.HTTPHandler()
        # proxy_support = urllib.request.ProxyHandler(proxies)
        # opener = urllib.request.build_opener(proxy_support, handler)
        # urllib.request.install_opener(opener)

        urllib.request.urlretrieve(url, fname)

        return fname

    except Exception as e:
        print(f"Unable to download: {url}. Exception: {e}")
        return None



def parse_pdf_text(pdf_path):

    ls_page_txt = []
    with pdfplumber.open(pdf_path) as pdf:
        # when passing list of pages to open it's 0-indexed
        # we already know want pages 2, 3 & 4
        total_pages = len(pdf.pages)
        for p in range(total_pages):
            cpage = pdf.pages[p]
            ctext = cpage.extract_text(layout=True)
            ls_page_txt.append(ctext)

    return ls_page_txt

# connection = get_db_connection()

for tag in soup.select('a.sens__link'):
    tag_text = tag.get_text()
    jse_url = tag['href']

    jse_url_parsed = urlparse(jse_url)
    jse_url_clean = unquote(jse_url_parsed.path)
    jse_output_name = os.path.basename(jse_url_clean)

    # setup output path so we can fix the duffix
    fout = stor_pth_hist / Path(jse_output_name)


    # first clear the existing extensinon
    filename_clear = fout.with_suffix("")
    # replace exrension with .pdf
    filename_pdf = filename_clear.with_suffix(".pdf")
    filename_txt = filename_clear.with_suffix(".txt")

    dl_file = None
    pages_string = ""

    if filename_pdf.exists():
        print(f"file: {filename_pdf} already downloaded")


    else:
        print(f"Downloading file to store: {jse_url}")
        dl_file = wdownload_file(jse_url, filename_pdf)

    if dl_file is not None:
        print("parsing pdf")
        ls_page_text = parse_pdf_text(dl_file)
        pages_string = "\n".join(ls_page_text)
        # save to db
        print(pages_string)
        print("saving to db")


        gpt_review = "todo"
        cur = connection.cursor()


        cur.execute("INSERT INTO sens (title, content, filename, gptreview) VALUES (?, ?, ?, ?)",
                    (tag_text,pages_string,str(filename_pdf),gpt_review)
                    )
        connection.commit()



    print(pages_string)



# cur = connection.cursor()

# cur.execute("INSERT INTO sens (title, content) VALUES (?, ?)",
#             ('First Post', 'Content for the first post')
#             )

# cur.execute("INSERT INTO sens (title, content) VALUES (?, ?)",
#             ('Second Post', 'Content for the second post')
#             )

# connection.commit()
connection.close()