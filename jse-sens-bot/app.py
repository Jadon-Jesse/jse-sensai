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
import datetime
# import re
from text_to_par import split_into_sentences
# from nltk import tokenize
import tiktoken





# HOST = os.environ.get("APP1_HOST_IP")
HOST = APP_HOST_IP
PORT = APP_HOST_PORT

stor_pth_hist = Path(".") / Path("store") / Path("dl-history")
stor_pth_hist.mkdir(parents = True, exist_ok = True)




app = Flask(__name__, static_url_path = "/jse-sens-bot/static")


app.config['SECRET_KEY'] = 'secret!'
app.config['TEMPLATES_AUTO_RELOAD'] = True
# app.jinja_env.filters['json'] = jinja2_escapejs_filter
# app.jinja_env.filters['test_call'] = test_func
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
You are the head of global markets for RMB. You are extremely witty, cleaver and everyone thinks you're hilarious. You love coming up with funny and attention grabbing titles for articles based on the article content, and it's original name. Your job is to come up with a more witty, meaningful and less verbose title based off the following article's contents and original title:
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
        "temperature":0.3,
        "metadata": msg_meta
    }

    return row_req


def build_sensai_go_review(row_id, title, body):
    prompt = f"""
You are the head of global market research for large south african hedge fund. You have made a lot of money throughout your career and you are always looking for opportunities to examine and critique the current news. You are also extremely sarcastic and love to brag about your time trading whenever you find the right moment. Your job is to provide a 10 line summery of the following SENS announcement from the JSE

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
        "temperature":0.7,
        "metadata": msg_meta
    }



    return row_req





def build_sensai_go_market_upate(sens):
    headlines = []
    for s in sens:
        headlines.append(s["gpttitle"])

    h = "\n ".join(headlines)

    prompt = f"""
You are an an award winning satirical comedian and financial news reporter. You are extremely cleaver and everyone thinks you're hilarious. Your job is to provide traders with a no more than 10 line market update describing whats been going on in the markets so far today. You should also try to identify hidden connections between various events that seem to be logically connected but may not be so obvious. Your market update should be succinct and will be based on the following highlights:
'''
{h}
'''
"""


    msg_request_list = [
        {'role': 'user', 'content': prompt}
    ]

    msg_meta = {
        # "row_id": row_id,
        "row_type":"market_update_review"
    }


    row_req = {
        # "model": "gpt-4",
        "model": "gpt-3.5-turbo",
        "messages": msg_request_list,
        "temperature":0.3,
        "metadata": msg_meta
    }

    return row_req




def build_sensai_go_title_market_upate(sens):
    headlines = []
    for s in sens:
        headlines.append(s["gpttitle"])

    h = "\n ".join(headlines)

    prompt = f"""
You are the lead editor for the daily financial report. You are renowned world wide for your satirical and attention grabbing headlines which are able to distill complex events and information into a single byte sized nuggets of information. Your job now is to take in the following market headlines and produce a single headline that ties it all together in your style:
'''
{h}
'''
"""


    msg_request_list = [
        {'role': 'user', 'content': prompt}
    ]

    msg_meta = {
        # "row_id": row_id,
        "row_type":"market_update_title"
    }


    row_req = {
        # "model": "gpt-4",
        "model": "gpt-3.5-turbo",
        "messages": msg_request_list,
        "temperature":0.3,
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
        # WebDriverWait(driver, delay).until(EC.presence_of_element_located((By.CLASS_NAME, "sens__link")))
        WebDriverWait(driver, delay).until(EC.presence_of_element_located((By.CLASS_NAME, "sensItemContainer")))
    except Exception as e:
        print(f"Exception while looking for elem: {e}")
        # return "Loading took too much time!"

    print("Getting soup")
    soup = BeautifulSoup(driver.page_source, "lxml")
    # print(soup)

    sens_announcements = []
    just_text_ls = []


    connection = get_db_connection()
    
    # for tag in soup.select('a.sens__link'):
    for tag in soup.select('li.sensItemContainer>a'):
        print(f"Processing tag: {tag}")
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


            
    connection.close()




def select_sens_to_ai():
    conn = get_db_connection()
    posts = conn.execute("SELECT * FROM sens WHERE gptreview = '-' AND gpttitle = '-' ").fetchall()
    conn.close()
    return posts



def run_gpt_async(in_jsonl, out_jsonl):
    results = None
    if in_jsonl.exists():
        print("Running")

        results = event_loop_thread.run_coroutine(
            my_api_request_parallel_processor.process_api_requests_from_file(
                requests_filepath=in_jsonl,
                save_filepath=out_jsonl,
                request_url="https://api.openai.com/v1/chat/completions",
                api_key=API_KEY,
                max_requests_per_minute=float(3_000 * 0.5),
                max_tokens_per_minute=float(250_000 * 0.5),
                token_encoding_name="cl100k_base",
                max_attempts=int(5),
                logging_level=int(logging.INFO),
            )
        )
        print("Results")
        print(results)
    else:
        results = None

    print("Done")
    return results


def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens



@app.route('/background_process_test')
def background_process_test():
    """How this works
    
    1. It will scrape the list of new sens and save the text into the database and mark the gpt fields as -
    2. We get the sens articles to be ai'd by looking for the ones with -
    3. build up the jsonl jobs so we can process in parallel. also tag each job with the database id so we can update it correctly
    4. save to file called temp.jsonl
    5. run the parallel process api request function to process jobs in parallel
    6. load the results from temp_out.jsonl
    7. Update the database with the respective gpt content

    NEXT we will do the similar but instead we will need the output from above to ceate the market update

    # how the market update should work

    # if there were new announcements processed
    # take all headlines from start of day up till that point 
    # create market update job based on the head lines
    # save to database





    Returns
    -------
    TYPE
        Description
    """


    print("async Hello")
    scrape_sel_edge_to_db()
    print("selecting sens")

    sens_articles = select_sens_to_ai()
    jobs = []
    new_ids = []

    # build up prompts and save to json l file
    # todo lock thread access
    for article in sens_articles:
        num_tokens = num_tokens_from_string(article["content"], "cl100k_base")
        print(article["title"])

        print(f"NUM Tokens: {num_tokens}")
        if num_tokens < 4097:
            # print(article["title"])
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




    print("trying to run async io ev loop in thread")

    filejs_out = Path.cwd() / Path("temp_out.jsonl")

    results = run_gpt_async(filejs, filejs_out)
    results_sens = results.result()


    print("Done running gpt async 1")


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
        # print("Request")
        # print(og_request)

        # print("Response")
        # print(response)

        # print("Meta")
        # print(meta)


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



    # GENERATE MARKET UPDATE based on all announcements for today up to now


    latest_sens_titles_for_mktupdate = get_latest_sens_for_market_update()

    for mkrow in latest_sens_titles_for_mktupdate:
        print(f"Days title: {mkrow['gpttitle']}")

    # every market update review will be a single job
    market_update_row_job_obj = build_sensai_go_market_upate(latest_sens_titles_for_mktupdate)
    # also build job to title based on same ai titles
    title_market_update_row_job_obj = build_sensai_go_title_market_upate(latest_sens_titles_for_mktupdate)

    ls_market_update_jobs = [market_update_row_job_obj, title_market_update_row_job_obj]

    # Now also save the mkupdate jobs to jsonl file for past processing
    filejs_mkudpt = Path.cwd() / Path("temp_mkudpt.jsonl")
    with open(filejs_mkudpt, "w") as f:
        for job in ls_market_update_jobs:
            json_string = json.dumps(job)
            f.write(json_string + "\n")


    # cool now again, paralell process again for the market update
    filejs_mkudpt_out = Path.cwd() / Path("temp_mkudpt_out.jsonl")
    
    print("runng market update async")
    future_results_mkupdt = run_gpt_async(filejs_mkudpt, filejs_mkudpt_out)
    results_mkupdt = future_results_mkupdt.result()
    print("done market update async. Loading")

    json_list_mkupdt = []
    with open(filejs_mkudpt_out, 'r') as json_file:
        json_list_mkupdt = list(json_file)




    market_update_review = ""
    market_update_title = ""


    for json_str in json_list_mkupdt:
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


        try:
            content = response['choices'][0]['message']['content']
            # print(content)
            # remove double quotes at start and end if exists
            no_dblquotes = content.strip('"')
            # remove single quotes at start and end if exists
            no_quotes = no_dblquotes.strip("'")
            # remove trailing white space
            clean_text = no_quotes.strip()



            if meta['row_type'] == "market_update_review":

                # save to db
                print("saving ai review to db")
                market_update_review = content

            if meta['row_type'] == "market_update_title":

                market_update_title = content

        except Exception as e:
            # removed fancy stuff
            print(e)

    # now insert the latest market update into the database
    print(f"MKTITLE: {market_update_title} - -{market_update_review}")

    # Insert into db - dont need to link right now
    # cause we can just always grab the latest one 

    connection = get_db_connection()
    cur = connection.cursor()



    cur.execute("INSERT INTO sens_market_update (gpttitle, gptcontent) VALUES (?, ?)",
                (market_update_title, market_update_review))
    connection.commit()
    connection.close()











    # return dict(data=ls_holder)
    return dict(data=[])



def get_sens_byids(id_list):
    conn = get_db_connection()
    sql="SELECT * FROM sens WHERE id in ({seq})".format(
        seq=','.join(['?']*len(id_list)))

    posts = conn.execute(sql, id_list).fetchall()
    conn.close()
    return posts



def get_latest_sens_for_market_update():
    conn = get_db_connection()
    # Get the start of the previous working day
    today = datetime.date.today()
    previous_working_day = today - datetime.timedelta(days=1)
    if previous_working_day.weekday() > 4:  # If the previous day is Saturday or Sunday, go back to Friday
        previous_working_day -= datetime.timedelta(days=previous_working_day.weekday() - 4)

    # Format the start of the previous working day as a datetime string
    start_of_previous_working_day = datetime.datetime.combine(previous_working_day, datetime.time())
    natitle = "-"
    print(f"previous_working_day: {start_of_previous_working_day}")
    # Execute the SQLite statement
    rows = conn.execute("SELECT gpttitle FROM sens WHERE created > ? AND gpttitle != ? ", (start_of_previous_working_day, natitle, )).fetchall()
    conn.close()
    return rows





def get_sens():
    conn = get_db_connection()
    today = datetime.date.today()
    previous_working_day = today - datetime.timedelta(days=1)
    if previous_working_day.weekday() > 4:  # If the previous day is Saturday or Sunday, go back to Friday
        previous_working_day -= datetime.timedelta(days=previous_working_day.weekday() - 4)

    # Format the start of the previous working day as a datetime string
    start_of_previous_working_day = datetime.datetime.combine(previous_working_day, datetime.time())
    posts = conn.execute('SELECT * FROM sens WHERE created > ? ORDER BY datetime(created) DESC', (start_of_previous_working_day, )).fetchall()

    # brek up sentences into paragraphs
    ls_posts = []
    for p in posts:
        row = dict(p)
        paragraphs = split_into_sentences(row['gptreview'])
        # print("OG")
        # print(row["gptreview"])
        # print("PARA")
        # print(paragraphs)
        row["gptreview"] = paragraphs
        ls_posts.append(row)

    market_update = conn.execute('SELECT * FROM sens_market_update ORDER BY datetime(created) DESC').fetchone()

    conn.close()
    # return posts, market_update
    return ls_posts, market_update






@app.route("/")
def hello_world():
    # stored_announcements = get_stored_announcements()
    print(f"Getting sens")
    sens, market_update = get_sens()
    # sensai = get_sensai(sens)
    # print(sens)
    # return render_template('index.html', jse_sens = sens, sensai=sensai)
    return render_template('index.html', jse_sens = sens, sensai=market_update, apiKey = API_KEY)


@app.route("/about")
def about():
    # stored_announcements = get_stored_announcements()
    print(f"About page")
    return render_template('about.html')

        



if __name__ == '__main__':
    try:
        print(f"Running on Host:{HOST} Port:{PORT}")

        app.run(host=HOST, port=int(PORT), debug=True)

    except Exception as e:
        print("Exception while stopping")
        print(e)