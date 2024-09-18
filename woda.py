#!/usr/bin/python3

import os
import sys
import requests
import re
import logging
import csv

from email.message import Message # for parsing content-disposition

import pdfplumber

logger = logging.getLogger("woda")

# List of docs below is from the page:
# https://www.gov.pl/web/wody-polskie/sytuacja-hydrologiczna
# 
# Other news from "Wody Polskie":
# https://www.gov.pl/web/wody-polskie/zbiorniki-wod-polskich-przygotowane-na-opady

html = """
<p><a href="https://www.gov.pl/attachment/0fad3d4a-e590-4e4b-a34a-871253ef3927">Skrócony komunikat o sytuacji hydrologiczno-meteorologicznej z dnia 16.09.2024 r. na godzinę 16:00</a></p>
<p><a href="https://www.gov.pl/attachment/8d832d68-8f9f-4818-a84f-37926cf1f708">Komunikat o sytuacji hydrologicznej z dnia 16.09.2024 r.</a></p>
<p><a href="https://www.gov.pl/attachment/794ff045-15a9-4ac0-b96b-ea320e50a97a">Skrócony komunikat o sytuacji hydrologiczno-meteorologicznej z dnia 15.09.2024 r. na godzinę 16:00</a></p>
<p><a href="https://www.gov.pl/attachment/8b8cb509-8c28-4593-8f49-cff18a16fba4">Komunikat o sytuacji hydrologicznej z dnia 15.09.2024 r.</a></p>
<p><a href="https://www.gov.pl/attachment/f900ed0b-f244-4a12-8a28-4aacb8eed71d">Skrócony komunikat o sytuacji hydrologiczno-meteorologicznej z dnia 14.09.2024 r. na godzinę 16:00</a></p>
<p><a href="https://www.gov.pl/attachment/13b927fa-b9bd-421d-a32f-b110ea21163d">Komunikat o sytuacji hydrologicznej z dnia 14.09.2024 r.</a></p>
<p><a href="https://www.gov.pl/attachment/14993d7b-f66b-456c-b426-83bb0a156b7e">Skrócony komunikat o sytuacji hydrologiczno-meteorologicznej z dnia 13.09.2024 r. na godzinę 14:00</a></p>
<p><a href="https://www.gov.pl/attachment/b88c0161-b95a-48e9-b042-847f0147b741">Komunikat o sytuacji hydrologicznej z dnia 13.09.2024 r</a></p>
<p><a href="https://www.gov.pl/attachment/f609a265-bcef-4a2c-ae62-b4fd20e393ba">Komunikat o sytuacji hydrologicznej z dnia 12.09.2024 r</a></p>
<p><a href="https://www.gov.pl/attachment/c001c4e3-944d-4606-b143-9c3a6e7c6f4f">Komunikat o sytuacji hydrologicznej z dnia 11.09.2024 r</a></p>
<p><a href="https://www.gov.pl/attachment/e2f94909-2ae1-4435-af08-5ab6261bc34a">Komunikat o sytuacji hydrologicznej z dnia 10.09.2024 r</a></p>
"""

def get_files(html: str) -> None:
    dpath = "./woda"
    os.makedirs(dpath, exist_ok=True)
    for m in re.finditer(r'<a href="(.*)">', html):
        url = m.group(1)
        logger.info(f"Downloading {url}")
        r = requests.get(url)
        # print headers
        print(r.headers)

        # Save file under the name from content-disposition field
        cd = r.headers.get("content-disposition", None)
        if cd is None:
            logging.warning(f"No content-disposition field, skipping {url}")
            continue

        msg = Message()
        msg['content-disposition'] = cd
        filename = msg.get_filename()

        with open(f"{dpath}/{filename}", "wb") as f:
            f.write(r.content)


def extract_data(pdf_file) -> list[list[str|None]]:
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

log_format = "%(asctime)s %(name)s %(levelname)s %(message)s"
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format=log_format,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# get_files(html)

all_rows = []

for file in os.listdir("woda"):
    if file.endswith(".pdf"):
        rows = extract_data(f"woda/{file}")
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
