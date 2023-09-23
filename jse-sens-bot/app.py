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
from pydantic import BaseModel, ValidationError
import openai
from concurrent.futures import ThreadPoolExecutor, as_completed
import event_loop_thread
import my_api_request_parallel_processor
# import nltk
import logging  # for logging rate limit warnings and other messages


class SensAI(BaseModel):
    gpt_title: str
    gpt_review: str



# HOST = os.environ.get("APP1_HOST_IP")
HOST = APP_HOST_IP
PORT = APP_HOST_PORT

stor_pth_hist = Path(".") / Path("store") / Path("dl-history")
stor_pth_hist.mkdir(parents = True, exist_ok = True)

openai.organization = "org-"
openai.api_key = "sk-"



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
    # conn.row_factory = row_to_dict
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


def build_sensai_go_title_review(row_id, title, body):
    prompt = f"""
You are the head of global markets for RMB. You are extremely witty, cleaver and everyone thinks you're hilarious. You love coming up with funny and attention grabbing titles for articles based on the article content, and it's original name. Your job is to come up with a more witty, meaninful and less verbose title based off the following article's contents and original title:
```
<originalTitle>
{title}
</originalTitle>

<articleContents>
{body}
</articleContents>
```
"""

    msg_request_list = [
        {'role': 'user', 'content': prompt}
    ]

    msg_meta = {
        "row_id": row_id,
        "row_type":"title"
    }


    row_req = {
        "model": "gpt-3.5-turbo",
        "messages": msg_request_list,
        "temperature":0,
        "metadata": msg_meta
    }



    return row_req


def sensai_go_title_review(ai_review, og_title):
    prompt = f"""
You are the head of global markets for RMB. You are extremely witty, cleaver and everyone thinks you're hilarious. You love coming up with funny and attention grabbing titles for articles based on the article content, and it's original name. Your job is to come up with a more witty and meaninful and less verbose title for the following article's contents and original title:
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
You are Jadon Manilall, the head of global markets for Rand Merchant Bank. You have made a lot of money throughout your career and gained a wealth of knowledge and experience about the South African markets which allows you to provide extremely subtle and nuanced views on current events. You're always looking for opportunities to examine and critique the current news and market events. You are also extremely funny and love to brag about your time trading during historic market events whenever you find the right moment. Your job now is to use your wit, creativity, experience and observational skills to provide a 10 line summery of the following SENS announcement from the JSE. Your summary should also make use of paragraphs for better readability.
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

# You are the head of global markets for Peresec Capital. You have made a lot of money throughout your career and you are always looking for opportunities to examine and critique the current news. You are also extremely sarcastic and love to brag about your time trading rolls whenever you find the right moment. Your job is to provide a 10 line summery of the following SENS announcement from the JSE:


def build_sensai_go_review(row_id, title, body):
    prompt = f"""
You are the head of global markets for Peresec Capital. You have made a lot of money throughout your career and you are always looking for opportunities to examine and critique the current news. You are also extremely funny you and love to make jokes about current events and announcements when you find the right moment for a hilarious punchline. Your job is to provide a 10 line summery of the following SENS announcement from the JSE:

'''
<title>
{title}
</title>
<body>
{body}
</body>
'''
"""

    msg_request_list = [
        {'role': 'user', 'content': prompt}
    ]

    msg_meta = {
        "row_id": row_id,
        "row_type":"review"
    }


    row_req = {
        "model": "gpt-3.5-turbo",
        "messages": msg_request_list,
        "temperature":0.9,
        "metadata": msg_meta
    }



    return row_req







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
            # first check if file alreay in db
            cur = connection.cursor()
            cur.execute("SELECT * FROM sens WHERE filename = ?", (str(filename_pdf),))
            data = cur.fetchone()

            if data is None:
                print("parsing pdf")
                ls_page_text = parse_pdf_text(dl_file)
                pages_string = "\n".join(ls_page_text)
                # print(pages_string_lines)

                # ai_title, ai_review = sensai_go(tag_text, pages_string)
                # calling gpt
                # ai_review = sensai_go_review(tag_text, pages_string)
                # ai_title = sensai_go_title_review(ai_review, tag_text)


                ai_review = "-"
                ai_title = "-"


                # save to db
                print("saving to db")


                cur.execute("INSERT INTO sens (title, content, filename, gptreview, gpttitle) VALUES (?, ?, ?, ?, ?)",
                            (tag_text,pages_string,str(filename_pdf),ai_review, ai_title)
                            )
                connection.commit()
                print("Done")
            else:
                print("Filename is already present in the database. Skipping insertion.")



        # print(pages_string)



            
    connection.close()


def process_article(article):
    # Make API request using openai.Completion.create()
    # response = openai.Completion.create(
    #     engine='text-davinci-003',
    #     prompt=article,
    #     max_tokens=100
    # )
    # generated_content = response.choices[0].text.strip()

    # return generated_content

    ai_review = sensai_go_review(article['title'], article['content'])
    ai_title = sensai_go_title_review(ai_review, article['title'])

    res = (article, ai_title, ai_review)
    return res


def select_sens_to_ai():
    conn = get_db_connection()
    posts = conn.execute("SELECT * FROM sens WHERE gptreview = '-' AND gpttitle = '-' ").fetchall()
    conn.close()
    return posts



def row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict:
    data = {}
    for idx, col in enumerate(cursor.description):
        data[col[0]] = row[idx]
    return data


@app.route('/background_process_test')
def background_process_test():
    print("async Hello")
    # scrape_sel_edge_to_db()
    print("selecting sens")

    sens_articles = select_sens_to_ai()
    jobs = []
    new_ids = []

    # build up prompts and save to json l file
    # todo lock thread access
    for article in sens_articles:
        row_request_obj_contet = build_sensai_go_review(article["id"], article["title"], article["content"])
        row_request_obj_title = build_sensai_go_title_review(article["id"], article["title"], article["content"])
        jobs.append(row_request_obj_contet)
        jobs.append(row_request_obj_title)

        new_ids.append(article['id'])


    # save as json l for the next step
    filejs = Path.cwd() / Path("temp.jsonl")
    with open(filejs, "w") as f:
        for job in jobs:
            json_string = json.dumps(job)
            f.write(json_string + "\n")



    # sens_articles = [
    # "article 1",
    # "article 2",
    # "article 3",
    # "article 4",

    # ]

    # Create a ThreadPoolExecutor
    # executor = ThreadPoolExecutor()

    # # Submit the articles to the executor for processing
    # futures = [executor.submit(process_article, article) for article in sens_articles]

    # # Wait for all the futures to complete
    # results = []
    # for future in as_completed(futures):
    #     result = future.result()
    #     results.append(result)


    # print("done bg async")
    # for r in results:
    #     print(r[0])
    #     print(r[1])
    #     print(r[2])



    # return dict(data=results)

    print("trying to run async io ev loop in thread")

    filejs_out = Path.cwd() / Path("temp_out.jsonl")


    # if filejs.exists():
    #     print("Running")

    #     results = event_loop_thread.run_coroutine(
    #         my_api_request_parallel_processor.process_api_requests_from_file(
    #             requests_filepath=filejs,
    #             save_filepath=filejs_out,
    #             request_url="https://api.openai.com/v1/chat/completions",
    #             api_key="sk-UoyeNYkQjEuP",
    #             max_requests_per_minute=float(3_000 * 0.5),
    #             max_tokens_per_minute=float(250_000 * 0.5),
    #             token_encoding_name="cl100k_base",
    #             max_attempts=int(5),
    #             logging_level=int(logging.INFO),
    #         )
    #     )
    #     print("Results")
    #     print(results)
    # print("Done")

    # now load back in the results that we just processed
    json_list = []
    with open(filejs_out, 'r') as json_file:
        json_list = list(json_file)


    print("loaded")
    connection = get_db_connection()
    for json_str in json_list:
        result = json.loads(json_str)
        # print(f"result: {result}")
        og_request = result[0]
        response = result[1]
        meta = result[2]
        print("Request")
        print(og_request)

        print("Response")
        print(response)

        print("Meta")
        print(meta)


        # clean up response and add to look up dict

        # lines = content.split("\n")


        clean_text = ""

        try:
            content = response['choices'][0]['message']['content']
            # print(content)
            # remove double quotes at start and end if exists
            no_dblquotes = content.strip('"')
            # remove single quotes at start and end if exists
            no_quotes = no_dblquotes.strip("'")
            # remove trailing white space
            clean_text = no_quotes.strip()

            if meta['row_type'] == "review":

                # save to db
                print("saving ai review to db")


                cur = connection.cursor()


                cur.execute("UPDATE sens SET gptreview = ? WHERE id = ?",
                    (content, meta['row_id'])
                )
                connection.commit()

            if meta['row_type'] == "title":

                # save to db
                print("saving ai title to db")


                cur = connection.cursor()


                cur.execute("UPDATE sens SET gpttitle = ? WHERE id = ?",
                    (content, meta['row_id'])
                )
                connection.commit() 






        except Exception as e:
            # removed fancy stuff
            print(e)
            clean_text = ""


    connection.close()

    # lastly get the uppdated sens
    sens = get_sens_byids(new_ids)

    ls_holder = []
    for s in sens:
        d = dict(s)
        print(d)
        ls_holder.append(d)


    # js_sens = json.dumps(ls_holder)


    return dict(data=ls_holder)
    # return render_template('index.html', jse_sens = sens)



def get_sens_byids(id_list):
    conn = get_db_connection()
    sql="select * from sens where id in ({seq})".format(
        seq=','.join(['?']*len(id_list)))

    posts = conn.execute(sql, id_list).fetchall()
    conn.close()
    return posts




def get_sens():
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM sens ORDER BY datetime(created) DESC').fetchall()
    conn.close()
    return posts



# def sensai_go_title_review(ai_review, og_title):




def get_sensai(sens):
    headlines = []
    for s in sens:
        headlines.append(s["gpttitle"])

    h = "\n ".join(headlines)

    p = f"""
You are an an award winning satarical comedian and financial news reporter. You are extremely witty, cleaver and everyone thinks you're hilarious. Your job is to provide traders with a no more than 10 line market update describing whats been going on in the markets so far today. You should also try to identify hidden connections between various events that seem to be logically connected but may not be so obvious. Your market update should be based on the following highlights:
'''
{h}
'''
"""


    chatCompletion = openai.ChatCompletion.create(
        # model="gpt-3.5-turbo", 
        model="gpt-4", 
        messages = [
            {'role': 'user', 'content': p}
        ],
        temperature = 0.9
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


@app.route("/")
def hello_world():
    # stored_announcements = get_stored_announcements()
    print(f"Getting sens")
    sens = get_sens()
    sensai = get_sensai(sens)
    # print(sens)
    return render_template('index.html', jse_sens = sens, sensai=sensai)


if __name__ == '__main__':
    try:
        print(f"Running on Host:{HOST} Port:{PORT}")

        app.run(host=HOST, port=int(PORT), debug=True)

    except Exception as e:
        print("Exception while stopping")
        print(e)