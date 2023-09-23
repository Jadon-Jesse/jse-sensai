import sqlite3
from bs4 import BeautifulSoup
from pathlib import Path

import urllib.request
import urllib.parse
import os
import json
import pdfplumber
from urllib.parse import urlparse, unquote

from pydantic import BaseModel, ValidationError
import openai

stor_pth_hist = Path(".") / Path("store") / Path("dl-history")
stor_pth_hist.mkdir(parents = True, exist_ok = True)

# openai.organization = "org-"
openai.api_key = "sk-"


connection = sqlite3.connect('database.db')



html = open("..\\SENS Announcements _ JSE Client Portal.html", "r", encoding="utf-8") 
source = html.read()
print(source)

soup = BeautifulSoup(source, "lxml")
# print(soup)

sens_announcements = []
just_text_ls = []




def sensai_go_title_review(ai_review, og_title):
    prompt = f"""
You are the head of global markets for RMB. You are extremely witty, cleaver and everyone thinks you're hilarious. You love coming up with funny and attention grabbing titles for articles based on the article content, and it's original name. Your job is to come up with a more suitable title for the following article:
```
<originalTitle>
{og_title}
</originalTitle>

<articleContents>
{ai_review}
</articleContents>
```
"""

    chatCompletion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages = [
            {'role': 'user', 'content': prompt}
        ],
        temperature = 0
    )

    content = chatCompletion['choices'][0]['message']['content']
    # lines = content.split("\n")


    clean_text = ""

    try:
        # remove double quotes at start and end if exists
        no_dblquotes = content.strip('"')
        # remove single quotes at start and end if exists
        no_quotes = no_dblquotes.strip("'")
        # remove trailing white space
        clean_text = no_quotes.strip()
    except Exception as e:
        last_exception = e
        error_msg = f"json.loads exception: {e}"
        print(error_msg)
        # removed fancy stuff
        clean_text = ""

    return clean_text


def sensai_go_review(title, body):
    prompt = f"""
You are Jadon Manilall, the head of global markets for Rand Merchant Bank. You have made a lot of money throughout your career and gained a wealth of knowledge and experience about the South African markets which allows you to provide extremely subtle and nuanced views on current events. You and you are always looking for opportunities to examine and critique the current news and market events. You are also extremely sarcastic and love to brag about your time trading during historic market events whenever you find the right moment. Your job now is to use your wit, creativity, and observational skills to provide a 5 to 10 line summery of the following SENS announcement from the JSE. Your summary should also be formatted well for end user readability.
```
<title>
{title}
</title>
<body>
{body}
</body>
```
"""

    chatCompletion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages = [
            {'role': 'user', 'content': prompt}
        ],
        temperature = 0
    )

    content = chatCompletion['choices'][0]['message']['content']
    # lines = content.split("\n")


    clean_text = ""

    try:
        # remove double quotes at start and end if exists
        no_dblquotes = content.strip('"')
        # remove single quotes at start and end if exists
        no_quotes = no_dblquotes.strip("'")
        # remove trailing white space
        clean_text = no_quotes.strip()
    except Exception as e:
        last_exception = e
        error_msg = f"json.loads exception: {e}"
        print(error_msg)
        # removed fancy stuff
        clean_text = ""

    return clean_text



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
        print("parsing pdf")
        ls_page_text = parse_pdf_text(filename_pdf)
        pages_string = "\n".join(ls_page_text)
        print(pages_string)

        print("gptting")
        ai_review = sensai_go_review(tag_text, pages_string)
        ai_title = sensai_go_title_review(ai_review, tag_text)

        # save to db
        print("saving to db")


        cur = connection.cursor()


        cur.execute("INSERT INTO sens (title, content, filename, gptreview, gpttitle) VALUES (?, ?, ?, ?,?)",
                    (tag_text,pages_string,str(filename_pdf),ai_review, ai_title)
                    )
        connection.commit()



    else:
        print(f"Downloading file to store: {jse_url}")
        dl_file = wdownload_file(jse_url, filename_pdf)

    if dl_file is not None:
        print("parsing pdf")
        ls_page_text = parse_pdf_text(dl_file)
        pages_string = "\n".join(ls_page_text)
        print(pages_string)

        print("gptting")
        ai_review = sensai_go_review(tag_text, pages_string)
        ai_title = sensai_go_title_review(ai_review, tag_text)

        # save to db
        print("saving to db")


        cur = connection.cursor()


        cur.execute("INSERT INTO sens (title, content, filename, gptreview, gpttitle) VALUES (?, ?, ?, ?,?)",
                    (tag_text,pages_string,str(filename_pdf),ai_review, ai_title)
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