from flask import (
    Flask, 
    render_template,
    request,
    Markup
)
# from flask_socketio import SocketIO, emit, disconnect

from pathlib import Path

import os
import json
import urllib.request
import urllib.parse

from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from appsecrets import (
    API_KEY,
    APP_HOST_IP,
    APP_HOST_PORT,
    APP_GECKO_DRIVER
)

# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup

import pdfplumber
from urllib.parse import urlparse, unquote
import base64

import sqlite3

# HOST = os.environ.get("APP1_HOST_IP")
HOST = APP_HOST_IP
PORT = APP_HOST_PORT

stor_pth_hist = Path(".") / Path("store") / Path("dl-history")
stor_pth_hist.mkdir(parents = True, exist_ok = True)


app = Flask(__name__, static_url_path = "/jse-sens-bot/static")

_js_escapes = {
        '\\': '\\u005C',
        '\'': '\\u0027',
        '"': '\\u0022',
        '>': '\\u003E',
        '<': '\\u003C',
        '&': '\\u0026',
        '=': '\\u003D',
        '-': '\\u002D',
        ';': '\\u003B',
        u'\u2028': '\\u2028',
        u'\u2029': '\\u2029'
}
# Escape every ASCII character with a value less than 32.
_js_escapes.update(('%c' % z, '\\u%04X' % z) for z in range(32))
def jinja2_escapejs_filter(value):
        retval = []
        for letter in value:
                if _js_escapes.has_key(letter):
                        retval.append(_js_escapes[letter])
                else:
                        retval.append(letter)

        return jinja2.Markup("".join(retval))
        
app.config['SECRET_KEY'] = 'secret!'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.filters['json'] = jinja2_escapejs_filter
# socketio = SocketIO(app, path="/jse-sens-bot/socket.io/")

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

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
        logger.debug(f"Unable to download: {url}. Exception: {e}")
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



def clean_str(dirty):
    clean0 = dirty.rstrip("\n")
    clean1 = str(clean0).strip()
    clean2 = clean1.replace("'", "")
    clean3 = clean2.replace('"', "")
    clean4 = clean3.replace('’', "")
    return clean4

def scrape_sel_edge():

    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")

    # options.headless = True  # Run Firefox in headless mode

    ff_driver_path = APP_GECKO_DRIVER
    ff_service = Service(ff_driver_path)
    driver = webdriver.Firefox(service=ff_service, options=options)


    url = "https://clientportal.jse.co.za/communication/sens-announcements"

    print("Using gecko")
    driver.get(url)

    html = driver.page_source

    print(html)

    delay = 40  # seconds
    try:
        # Wait until the dynamically loaded elements are loaded.
        WebDriverWait(driver, delay).until(EC.presence_of_element_located((By.CLASS_NAME, "sens__link")))
    except Exception as e:
        print(f"Exception while looking for elem: {e}")
        # return "Loading took too much time!"

    print("Getting soup")
    soup = BeautifulSoup(driver.page_source, "lxml")
    # print(soup)

    sens_announcements = []
    just_text_ls = []
    
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
            # dl_file = filename_pdf
            with open(filename_txt, encoding='utf-8') as f:
              # pages_string = " ".join([l.rstrip("\n") for l in f]) 
              pages_string = " ".join([ clean_str(l) for l in f]) 


        else:
            print(f"Downloading file to store: {jse_url}")
            dl_file = wdownload_file(jse_url, filename_pdf)

        if dl_file is not None:
            print("parsing pdf")
            ls_page_text = parse_pdf_text(dl_file)
            pages_string_lines = "\n".join(ls_page_text)
            # save to file
            with open(filename_txt, "w", encoding='utf-8') as text_file:
                text_file.write(pages_string_lines)


            with open(filename_txt, encoding='utf-8') as f:
              # pages_string = " ".join([l.rstrip("\n") for l in f]) 
              pages_string = " ".join([clean_str(l) for l in f]) 


        print(pages_string)





        announcement = {
            'akey':API_KEY,
            'text': tag_text,
            'href': jse_url,
            'body':pages_string

        }
        sens_announcements.append(announcement)
        just_text_ls.append(tag_text)

    # if the announcements are empty for the day - use old one
    if len(sens_announcements) == 0:
        print('using old sens')
        old_files = stor_pth_hist.glob("*.txt")
        num_old = 10
        for (i, oldf) in enumerate(old_files):
            if i>num_old:
                break
            pages_string = ""

            print(f"file: {oldf.stem} already downloaded")
            # dl_file = filename_pdf
            with open(oldf, encoding='utf-8') as f:
              # pages_string = " ".join([l.rstrip("\n") for l in f]) 
              pages_string = " ".join([ clean_str(l) for l in f]) 

            announcement = {
                'akey':API_KEY,
                'text': oldf.stem,
                'href': oldf.stem,
                'body':pages_string

            }
            sens_announcements.append(announcement)



            
    # driver.quit()

    # return json.dumps(sens_announcements)
    return sens_announcements, just_text_ls




def scrape_sel_edge_to_db():

    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")

    # options.headless = True  # Run Firefox in headless mode

    ff_driver_path = APP_GECKO_DRIVER
    ff_service = Service(ff_driver_path)
    driver = webdriver.Firefox(service=ff_service, options=options)


    url = "https://clientportal.jse.co.za/communication/sens-announcements"

    print("Using gecko")
    driver.get(url)

    html = driver.page_source

    print(html)

    delay = 40  # seconds
    try:
        # Wait until the dynamically loaded elements are loaded.
        WebDriverWait(driver, delay).until(EC.presence_of_element_located((By.CLASS_NAME, "sens__link")))
    except Exception as e:
        print(f"Exception while looking for elem: {e}")
        # return "Loading took too much time!"

    print("Getting soup")
    soup = BeautifulSoup(driver.page_source, "lxml")
    # print(soup)

    sens_announcements = []
    just_text_ls = []


    connection = get_db_connection()
    
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
            # print(pages_string_lines)
            print("saving to db")


            gpt_review = "todo"
            cur = connection.cursor()


            cur.execute("INSERT INTO sens (title, content, filename, gptreview) VALUES (?, ?, ?, ?)",
                        (tag_text,pages_string,filename_pdf,gpt_review)
                        )
            connection.commit()



        print(pages_string)



            
    connection.close()
    


def get_stored_announcements():
    announcements = []
    files = stor_pth_hist.glob("*.txt")
    for file in files:
        with open(file, encoding='utf-8') as f:
            pages_string = " ".join([clean_str(l) for l in f])
            announcement = {
                'akey': API_KEY,
                'text': file.stem,
                'href': file.stem,
                'body': pages_string
            }
            announcements.append(announcement)
    return announcements


# background process happening without any refreshing
@app.route('/background_process_test')
def background_process_test():
    print ("Hello")
    scrape_sel_edge_to_db()

    return dict(data="stuff")


def get_sens():
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM sens').fetchall()
    conn.close()
    return posts

@app.route("/")
def hello_world():
    stored_announcements = get_stored_announcements()
    print(f"Getting sens")
    sens = get_sens()
    print(sens)
    return render_template('index.html', jse_sens = sens)


if __name__ == '__main__':
    try:
        print(f"Running on Host:{HOST} Port:{PORT}")

        app.run(host=HOST, port=int(PORT), debug=True)

    except Exception as e:
        print("Exception while stopping")
        print(e)