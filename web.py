#!/usr/bin/python3

import os
import sys
import csv
import locale
import uvicorn

from typing import cast
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
    for n in ["outflow", "inflow", "volume", "normal_volume", "max_volume"]:
        try:
            row[n] = float(row.get(n, 0))
        except (ValueError, TypeError):
            row[n] = None
    max_volume = cast(float, row["max_volume"])
    volume = cast(float, row["volume"])
    if max_volume and volume:
        row["volume_percent"] = volume / max_volume * 100
    else:
        row["volume_percent"] = None

def round_up(n):
    digs = len(str(int(n))) - 2
    return round(n + 0.5*(10**digs), -digs)

class MainUI:
    grid: ui.aggrid
    data: list[dict]

    def __init__(self, data: list[dict]):
        self.data = data

    @classmethod
    def init_nice_gui(cls, fastapi_app: FastAPI, data: list[dict]):
        @ui.page("/")
        async def root():
            main_ui = MainUI(data)
            await main_ui.render_page()

        @app.on_startup
        async def app_startup():
            ...

        @app.on_shutdown
        async def app_shutdown():
            ...

        ui.run_with(fastapi_app, title="Woda")

    async def render_page(self):

        ui.add_head_html(
            '<style>\n'
            'div.nicegui-echart {\n'
            '  position: absolute;\n'
            '  left: 0;\n'
            '  top: 0;\n'
            '  right: 0;\n'
            '  bottom: 0;\n'
            '}\n'
            '</style>\n'
        )

        self.main_content = ui.column().classes("h-[90vh] w-full")

        with ui.footer(), ui.row().classes("flex w-full"):
            URL = "https://www.gov.pl/web/wody-polskie/sytuacja-hydrologiczna/"
            ui.label("Dane pochodzą ze strony: ")
            ui.link(URL, URL, new_tab=True).classes("text-white")
            ui.space().classes("flex-grow")
            ui.label("Pobierz surowe dane (CSV)").on(
                "click", lambda: ui.download("woda.csv")
            ).classes("cursor-pointer text-white")
            ui.space().classes("flex-grow")
            ui.label("Kontakt: Piotr Piątkowski, pp@idea7.pl")

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
                return

            ui.label(
                f"Obiekt: {selected['name']} ({selected['river']})"
            ).classes("font-bold")

            chart_data = [
                row for row in self.data 
                if row["name"] == selected["org_name"] 
                and row["river"] == selected["river"]
            ]
            print(len(chart_data))
            print(chart_data)
            max_volume = max(row["max_volume"] for row in chart_data
                             if row["max_volume"] is not None)
            top_volume = max(row["volume"] for row in chart_data
                                if row["volume"] is not None)

            series = []
            for i, (field, name) in enumerate([
                ("inflow", "Dopływ"),
                ("outflow", "Odpływ"),
                ("volume", "Wypełnienie"),
                #"volume_percent",
            ]):
                sdata = {
                    "type": "line",
                    "showSymbol": True,
                    "name": name,
                    "yAxisIndex": 1 if field == "volume" else 0,
                    "data": [
                        [
                            r["timestamp"] * 1000,
                            r[field],
                        ]
                        for r in sorted(chart_data, key=lambda x: x["timestamp"])
                    ],
                }

                if field == "volume":
                    sdata["markLine"] = {
                        "data": [
                            {
                                "name": "Maksymalna pojemność powodziowa",
                                "yAxis": max_volume,
                                "symbol": "none",
                                "lineStyle": {
                                    "color": "red",
                                    "type": "dashed",
                                },
                            },
                        ],
                    }

                series.append(sdata)

            chart_data = {
                "animation": False,
                "legend": {
                    "show": True,
                    "top": 10,
                },
                "tooltip": {
                    "show": True,
                },
                "xAxis": {
                    "type": "time",
                    "nameLocation": "center",
                    "axisLabel": {
                        "align": "left",
                        "padding": [0, 0, 0, 10],
                        "formatter": "{dd}-{MM}-{yyyy}",
                    },
                    "splitArea": {
                        "show": True,
                    },
                },
                "yAxis": [
                    {
                        "type": "value",
                        "name": "Przepływ\n\n[m³/s]",
                        "min": 0,
                        "alignTicks": True,
                        "position": "left",
                        "axisLine": {
                            "show": True,
                        },
                    },
                    {
                        "type": "value",
                        "name": "Wypełnienie\n\n[mln m³]",
                        "min": 0,
                        "max": round_up(max(max_volume, top_volume)),
                        "alignTicks": True,
                        "position": "right",
                        "axisLine": {
                            "show": True,
                        },
                        "axisLabel": {
                            ":formatter": "(v) => v.toFixed(2)",
                        },
                    },
                ],
                "series": series,
            }
            print(chart_data)
            with ui.card().classes("w-full h-[500px]"):
                self.chart = ui.echart(chart_data).classes("h-full")


fapp = FastAPI()
MainUI.init_nice_gui(fapp, data)

uvicorn.run(
    fapp,
    host="0.0.0.0",
    port=8080,
    workers=1,
    reload=False,
)
