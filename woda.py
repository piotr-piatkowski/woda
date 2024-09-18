#!/usr/bin/python3

import os
import sys
import requests
import re
import logging
import csv

from email.message import Message # for parsing content-disposition

import pdfplumber

# Other news from "Wody Polskie":
# https://www.gov.pl/web/wody-polskie/zbiorniki-wod-polskich-przygotowane-na-opady

SRC_URL = "https://www.gov.pl/web/wody-polskie/sytuacja-hydrologiczna"
FILES_LIMIT = 10
WORK_DIR = "./woda"

logger = logging.getLogger("woda")

def get_files() -> None:
    html = requests.get(SRC_URL).text

    idx = html.find('Sytuacja hydrologiczna')
    if idx == -1:
        logger.error("Cannot find 'Sytuacja hydrologiczna' section")
        return
    
    html = html[idx:]

    os.makedirs(WORK_DIR, exist_ok=True)
    n = 0
    for m in re.finditer(r'<a [^>]*?href="(.*/attachment/.*)">', html):
        if n >= FILES_LIMIT:
            break

        url = m.group(1)
        if url.startswith('/'):
            url = f"https://www.gov.pl{url}"

        logger.info(f"Downloading {url}")
        r = requests.get(url)
        assert r.status_code == 200

        # Save file under the name from content-disposition field
        cd = r.headers.get("content-disposition", None)
        if cd is None:
            logging.warning(f"No content-disposition field, skipping {url}")
            continue

        msg = Message()
        msg['content-disposition'] = cd
        filename = msg.get_filename()

        with open(f"{WORK_DIR}/{filename}", "wb") as f:
            f.write(r.content)

        n += 1


def extract_file_data(pdf_file) -> list[list[str|None]]:
    timestamp = None
    OPTS = {
        "snap_x_tolerance": 10,
        "snap_y_tolerance": 6,
        "horizontal_strategy": "lines",
    }
    table_rows = None
    with pdfplumber.open(pdf_file) as pdf: 
        for page in pdf.pages:
            table = page.find_table(OPTS)
            if not table:
                continue

            # Add explicit horizontal line at the top of table,
            # otherwise some cells are not detected between pages.
            top_line = table.bbox[1]
            table = page.find_table(
                {**OPTS, "explicit_horizontal_lines": [top_line]}
            )
            assert table is not None
            tdata = table.extract()

            for row in tdata:
                row = row[1:] # skip first column
                if table_rows is None:
                    txt = ''.join(c for c in row if c is not None)
                    if txt.startswith("Zbiorniki retencyjne"):
                        table_rows = [row]
                else:
                    if all(c is None for c in row[1:]):
                        # sometimes row is split into two or even three rows,
                        # only first column has value so in such case we merge
                        # it to the previous row, then ignore the rest
                        if row[0] != '' and table_rows[-1][0] == '':
                            table_rows[-1][0] = row[0]
                    else:
                        table_rows.append(row)

        assert table_rows is not None
        return table_rows


def extract_all_data():
    all_rows = []

    for file in os.listdir(WORK_DIR):
        if file.endswith(".pdf"):
            rows = extract_file_data(f"{WORK_DIR}/{file}")
            dttxt = rows[1][1]
            assert dttxt is not None
            m = re.search(
                r"(\d{2})\.(\d{2})\.(\d{4}) r\. na godz\. (\d?\d)(\d\d)", dttxt
            )
            assert m is not None, dttxt
            d, m, y, hh, mm = m.groups()
            ts = f"{y}-{m}-{d} {int(hh):02d}:{mm}:00"

            for row in rows[5:]:
                assert row[1] is not None
                name = row[1].replace('\n', ' ')
                m = re.match(r'(.*?)\s*\((.*)\)', name)
                assert m
                name, river = m.groups()
                name = name.replace('*', '').strip()
                vals = [str(v).replace(',', '.') for v in row[2:7]]
                row = [ts, name, river] + vals
                print(row)
                all_rows.append(row)

    with open("woda.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "name",
                "river",
                "outflow",
                "inflow",
                "volume",
                "normal_volume",
                "max_volume",
            ]
        )
        for row in all_rows:
            writer.writerow(row)


log_format = "%(asctime)s %(name)s %(levelname)s %(message)s"
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format=log_format,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# get_files()
extract_all_data()