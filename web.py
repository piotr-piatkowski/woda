#!/usr/bin/python3

import os
import sys
import csv
import locale
import uvicorn

from fastapi import FastAPI
from datetime import datetime
from nicegui import ui, app

DATA_FILE = "woda.csv"

locale.setlocale(locale.LC_COLLATE, "pl_PL.UTF-8")

# Load data from the CSV file as dictionaries
with open(DATA_FILE, "r") as f:
    reader = csv.DictReader(f)
    data = list(reader)

objects = set( (row["name"], row["river"]) for row in data)
objects = [{"name": name, "river": river} for name, river in objects]

for obj in objects:
    obj["org_name"] = obj["name"]
    obj["name"] = obj["name"].replace("Zb. ", "")

for row in data:
    row["timestamp"] = int(
        datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S").timestamp()
    )

class MainUI:
    grid: ui.aggrid

    @classmethod
    def init_nice_gui(cls, fastapi_app: FastAPI):
        @ui.page("/")
        async def root():
            main_ui = MainUI()
            await main_ui.render_page()

        @app.on_startup
        async def app_startup():
            ...

        @app.on_shutdown
        async def app_shutdown():
            ...

        ui.run_with(fastapi_app, title="Woda")

    async def render_page(self):

        self.main_content = ui.column().classes("h-[90vh] w-full")

        # with ui.header():
        #     ui.label("Dane o zapełnieniu i przepływach w zbiornikach retencyjnych").classes("font-bold w-full text-center text-2xl")

        # with ui.footer():
        #     ui.label("Autor: Piotr Piątkowski, 2024").classes("w-full text-right text-sm font-italic")

        with ui.left_drawer().classes("h-screen w-1/4"):
            ui.label("Wybierz obiekt:").classes("font-bold")

            self.grid = ui.aggrid(
                {
                    "accentedSort": True,
                    "defaultColDef": {
                        "flex": 1,
                        "resizable": True,
                        "filter": True,
                        "sortable": True,
                        "sortingOrder": ["asc", "desc"],
                    },
                    "columnDefs": [
                        {
                            "field": "name",
                            "headerName": "Zbiornik",
                            "sort": "asc",
                        },
                        {
                            "field": "river",
                            "headerName": "Rzeka",
                        },
                    ],
                    "rowData": objects,
                    "rowSelection": "single",
                }
            )
            self.grid.classes("h-full")
            self.grid.on("selectionChanged", self.render_main)

    async def render_main(self):
        self.main_content.clear()
        with self.main_content:
            selected = await self.grid.get_selected_row()
            if selected is None:
                ui.label("Wybierz obiekt z listy").classes("font-bold")
            else:
                ui.label(
                    f"Obiekt: {selected['name']} ({selected['river']})"
                ).classes("font-bold")
            print(selected)


fapp = FastAPI()
MainUI.init_nice_gui(fapp)

uvicorn.run(
    fapp,
    host="0.0.0.0",
    port=8080,
    workers=1,
    reload=False,
)
