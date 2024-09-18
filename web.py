#!/usr/bin/python3

import os
import sys
import csv
import locale

from datetime import datetime
from nicegui import ui

DATA_FILE = "woda.csv"

locale.setlocale(locale.LC_COLLATE, "pl_PL.UTF-8")

# Load data from the CSV file as dictionaries
with open(DATA_FILE, "r") as f:
    reader = csv.DictReader(f)
    data = list(reader)

objects = set( (row["name"], row["river"]) for row in data)
objects = sorted(objects, key=lambda r: locale.strxfrm(r[0]) or locale.strxfrm(r[1]))
objects = [{"name": name, "river": river} for name, river in objects]

for obj in objects:
    obj["org_name"] = obj["name"]
    obj["name"] = obj["name"].replace("Zb. ", "")

for row in data:
    row["timestamp"] = int(
        datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S").timestamp()
    )

def render_page():

    with ui.left_drawer().classes("h-screen"):
        ui.label("Wybierz obiekt:").classes("font-bold")

        grid = ui.aggrid(
            {
                "defaultColDef": {"flex": 1, "resizable": True},
                "columnDefs": [
                    {
                        "field": "name",
                        "headerName": "Zbiornik",
                        "filter": True,
                        "sortable": True,
                        ":comparator": 
                            "(vA, vB, nA, nB, desc) => "
                            "vA.localeCompare(vB)",
                    },
                    {
                        "field": "river",
                        "headerName": "Rzeka",
                        "filter": True,
                        "sortable": True,
                        ":comparator": 
                            "(vA, vB, nA, nB, desc) => "
                            "vA.localeCompare(vB)",
                    },
                ],
                "rowData": objects,
                "rowSelection": "single",
            }
        ).classes("h-full")

render_page()
ui.run(reload=True, title="Woda")
