"""
Cape Breton People and Traditions Map
=====================================

Developer overview
------------------

This script builds a complete standalone interactive HTML map application from
four CSV files:

    - places.csv
    - people.csv
    - communities.csv
    - traditions.csv

The output is:

    - cape_breton_people_map.html

The generated HTML file is self-contained. It includes:
    - the full page HTML structure
    - embedded CSS styling
    - embedded Plotly JavaScript library
    - embedded JavaScript logic for interactivity
    - embedded map data and lookup data exported from Python as JSON

In other words, this Python script is both:
    1. a data-processing script
    2. a static web-app generator


High-level pipeline
-------------------

The script runs in five broad stages:

1. Read and clean CSV data
2. Build structured lookups for places, people, and traditions
3. Build Plotly map figures in Python
4. Inject those figures and lookups into HTML/JS/CSS template text
5. Write the finished standalone HTML file to disk


Input files and their roles
---------------------------

places.csv
    Master place list. Supplies place keys, place names, and coordinates.
    Also provides bilingual place-name splitting where names are stored in a
    single "Gaelic | English" field.

people.csv
    Supplies informant/person records linked to places by "Place number".
    This drives:
        - the "Location details" list of people
        - the "List All People" alphabetical index

communities.csv
    Links Cape Breton community keys to associated tradition keys.

traditions.csv
    Links tradition keys to the Cape Breton communities associated with them,
    and supports the Scotland inset map and tradition overlays.


Main data flow
--------------

The cleaned data moves through the script in this order:

    raw CSVs
        -> cleaned DataFrames
        -> Python lookup structures
        -> Plotly figure specs
        -> JSON embedded in HTML/JS
        -> finished browser application


Function-by-function guide
--------------------------

Utility helpers
~~~~~~~~~~~~~~~

cleaned_text(value)
    Normalises text values from CSV input.
    Converts None / NaN / "nan" into empty string and trims whitespace.

first_present_value(row, column_names)
    Searches across several possible column names and returns the first
    non-empty value. Used mainly for dates, where source columns may vary.

parse_number_list(value)
    Converts comma-separated numeric strings into Python integer lists.
    Used for parsing community/tradition relationship fields.

split_bilingual_name(value)
    Splits a place label of the form:
        "Gaelic name | English name"
    into:
        (gaelic_name, english_name)

format_bilingual_plain(gaelic, english)
    Returns a plain bilingual label for hover text or simple display.


Cleaning functions
~~~~~~~~~~~~~~~~~~

clean_places(df)
    Cleans places.csv by:
        - removing unnamed columns
        - normalising column names
        - validating required columns
        - coercing coordinates and keys to numeric types
        - removing incomplete rows
        - splitting bilingual place names into separate Gaelic/English fields

    Output:
        cleaned places dataframe with:
            place_key
            place_name
            place_name_gaelic
            place_name_english
            latitude
            longitude

clean_people(df)
    Cleans people.csv by:
        - validating "Place number"
        - converting place keys to integers
        - normalising all text fields
        - constructing:
            gaelic_name
            english_name
            display_name
            sort_name

    This cleaned dataframe is the main source for all person/informant display.

clean_communities(df)
    Cleans communities.csv by:
        - validating columns
        - coercing Community to integer
        - parsing linked tradition IDs into Tradition_keys list

clean_traditions(df)
    Cleans traditions.csv by:
        - validating columns
        - coercing Tradition to integer
        - parsing linked community IDs into Community_keys list


Lookup-building functions
~~~~~~~~~~~~~~~~~~~~~~~~~

build_people_lookup(people_df)
    Creates a dictionary keyed by place number.
    Each value is a list of people attached to that place.

    This powers the "Location details" panel when a map marker is clicked.

build_all_people_index(people_df, places_df)
    Creates a flat list of all people, including:
        - names
        - ID
        - dates
        - place of origin
        - coordinates
        - sort letter and sort key

    This powers the "List All People" tab.

build_community_tradition_lookup(communities_df, traditions_df, all_places_df)
    Creates a lookup from Cape Breton community/place key to the traditions
    associated with that place.

    This powers:
        - "Associated traditions" in the side panel
        - overlay controls shown for the selected place

build_tradition_overlay_specs(...)
    Creates a structured list describing each tradition overlay, including:
        - tradition key
        - label text
        - assigned colour
        - linked Cape Breton points
        - linked Scotland point
        - hover content

    This is the bridge between relationship data and actual map traces.


Map-building functions
~~~~~~~~~~~~~~~~~~~~~~

make_main_figure(places_df, tradition_specs)
    Builds the main Cape Breton Plotly map.

    It adds:
        1. base place markers
        2. two empty highlight traces used for the selected-place ring
        3. one hidden trace per tradition overlay

    Important:
        The overlay traces already exist in the figure at generation time.
        JavaScript later only toggles their visibility.

make_inset_figure(tradition_specs)
    Builds the Scotland inset Plotly map.

    It adds:
        1. two empty highlight traces for inset selection
        2. one hidden Scotland marker trace per tradition

    Again, Python creates all layers in advance; browser-side JavaScript
    switches them on and off.


HTML / CSS / JavaScript generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

render_html(...)
    This is the core page-generation function.

    It does all of the following:

    1. Converts Plotly figures into serialisable dictionaries
       using:
           main_fig.to_dict()
           inset_fig.to_dict()

    2. Embeds the Plotly JavaScript library directly into the page using:
           get_plotlyjs()

       This makes the output HTML self-contained.

    3. Builds browser-side lookup objects in Python, including:
           places_lookup
           overlay_controls_all

    4. Injects Python data structures into JavaScript using json.dumps(...)

       Example:
           const placesLookup = {json.dumps(places_lookup, ensure_ascii=False)};

       This is the main bridge from Python data to browser logic.

    5. Writes the full page as a single large f-string containing:
           - <style> ... </style>
           - page HTML markup
           - <script> ... </script>

    6. Saves the completed HTML file to disk.

    In practical terms:
        render_html() is the function that generates the web app.


What in this script generates the HTML?
---------------------------------------

The HTML markup is generated directly inside the large f-string in render_html().

That includes visible page structure such as:
    - banner/header
    - side-panel tabs
    - location details panel
    - all-people panel
    - map container
    - inset panel
    - overlay panel
    - buttons, wrappers, and labels

So if a visible page element exists in the final HTML file, it is most likely
written as literal markup inside render_html().


What in this script generates the CSS?
--------------------------------------

The CSS is also generated inside render_html(), in the embedded <style> block.

Python constants such as:
    ACCENT
    BODY_TEXT
    BANNER_BG
    TITLE_COLOUR
are interpolated directly into that CSS.

There is no separate stylesheet. The final HTML contains all styles inline.


What in this script generates the JavaScript?
---------------------------------------------

The JavaScript is generated inside render_html(), in the embedded <script> block.

There are two parts to this:

1. Data exported from Python into JS
   Examples:
       const mainFigureSpec = ...
       const placesLookup = ...
       const peopleByPlace = ...
       const allPeopleIndex = ...
       const overlayControlsAll = ...

   These are produced by json.dumps(...) on Python objects.

2. Handwritten browser logic embedded in the HTML template
   This includes functions for:
       - rendering place details
       - rendering the all-people list
       - selecting people
       - toggling traditions
       - managing overlay visibility
       - showing/hiding inset and overlay panels
       - wiring up click handlers
       - initialising Plotly maps

So:
    Python prepares the data
    JavaScript handles interactivity in the browser


Key browser-side responsibilities
---------------------------------

Once the HTML file is opened, the embedded JavaScript takes over and handles:

    - creating the Plotly maps from embedded figure specs
    - reacting to map marker clicks
    - filling the "Location details" panel
    - filling the "List All People" panel
    - selecting a person and highlighting their place
    - showing/hiding associated traditions
    - showing/hiding overlay and inset panels
    - updating selected-place labels
    - redrawing traces when overlays are toggled


Why Plotly is created in Python first
-------------------------------------

The figures are built in Python so that:
    - all traces are prepared from cleaned data
    - trace ordering is known and stable
    - colours and hover data are assigned centrally
    - the browser only has to render and toggle visibility

In short:
    Python constructs the map specification
    JavaScript uses that specification interactively


Main entry point
----------------

main()
    This is the orchestration function.

    It:
        - resolves file paths
        - reads each CSV
        - cleans all input data
        - derives the Cape Breton place subset
        - calculates people counts
        - builds all lookup structures
        - builds the main and inset Plotly figures
        - calls render_html(...)
        - writes the final HTML file

    If you need to understand the execution order of the whole script,
    start with main().


Practical editing guide
-----------------------

If you want to change data logic:
    edit the cleaning functions or lookup-building functions

If you want to change what appears on the maps:
    edit:
        make_main_figure()
        make_inset_figure()
        build_tradition_overlay_specs()

If you want to change layout, styling, or browser behaviour:
    edit render_html(), specifically:
        - the <style> block for CSS
        - the HTML markup for structure
        - the <script> block for JavaScript logic

If you want to change colours, banner sizes, or defaults:
    edit the constants near the top of the file


Mental model
------------

Think of this script as a build system for a small standalone web app:

    CSV data
        -> cleaned Python structures
        -> Plotly figures + JSON lookups
        -> single generated HTML file
        -> interactive browser application

"""


import json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

PLACES_CSV = "places.csv"
PEOPLE_CSV = "people.csv"
COMMUNITIES_CSV = "communities.csv"
TRADITIONS_CSV = "traditions.csv"
OUTPUT_HTML = "cape_breton_people_map.html"
BASE_URL = "13.62.226.132"

MAP_CENTER = {"lat": 46.25, "lon": -60.65}
MAP_ZOOM = 7.8

SCOTLAND_CENTER = {"lat": 56.75, "lon": -4.6}
SCOTLAND_ZOOM = 4.6

ACCENT = "#8CC7EA"
TITLE_COLOUR = "#1F5F99"
BODY_TEXT = "#192930"
PANEL_BG = "#ffffff"
CARD_BG = "#ffffff"
BORDER = "#ffffff"
BANNER_BG = "#2184c2"
BANNER_GAELIC = "#ffffff"

BANNER_HEIGHT = 170

TRADITION_COLOURS = [
    "#C6283E",  # red
    "#E0322B",  # reddish orange
    "#D86A2C",  # orange
    "#E3A33C",  # orange yellow
    "#E0C341",  # yellow
    "#D6D645",  # greenish yellow
    "#7EA63C",  # yellow green
    "#4C9A3D",  # green
    "#3F5E2B",  # olive green
    "#6E3B8B",  # purple
    "#5B4BA8",  # violet
    "#8A2C83",  # purplish red
    "#C97AA4",  # purplish pink
    "#D78C73",  # yellowish pink
    "#8E1C1C",  # reddish brown
    "#7B3F00",  # yellowish brown
    "#8F6C3A",  # earthy brown
    "#C7BC8A",  # buff
    "#8A8A8A",  # grey
    "#B94E6F",  # dusty rose
    "#7D5A50",  # muted clay
    "#6A4C93",  # deep lavender
    "#00A86B"   # wildcard: vivid jade green
]


def cleaned_text(value: Any) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def first_present_value(row: pd.Series, column_names: list[str]) -> str:
    for col in column_names:
        if col in row.index:
            value = cleaned_text(row.get(col, ""))
            if value:
                return value
    return ""


def parse_number_list(value: Any) -> list[int]:
    text = cleaned_text(value)
    if not text:
        return []
    results: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            results.append(int(float(part)))
        except ValueError:
            continue
    return results


def split_bilingual_name(value: str) -> tuple[str, str]:
    if "|" in value:
        left, right = value.split("|", 1)
        return left.strip(), right.strip()
    return value.strip(), ""


def format_bilingual_plain(gaelic: str, english: str) -> str:
    if gaelic and english:
        return f"{gaelic} | {english}"
    return gaelic or english or ""


def clean_places(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.loc[:, ~df.columns.str.contains(r"^Unnamed", case=False, na=False)]
    df.columns = [str(c).strip() for c in df.columns]

    rename_map = {
        "Place Number": "place_key",
        "Community of Origin (Canada)": "place_name",
        "Latitiude": "latitude",
        "Latitude": "latitude",
        "Longitude": "longitude",
    }
    df = df.rename(columns=rename_map)

    required = ["place_key", "place_name", "latitude", "longitude"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"places.csv is missing required column(s): {missing}")

    df["place_key"] = pd.to_numeric(df["place_key"], errors="coerce").astype("Int64")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["place_name"] = df["place_name"].map(cleaned_text)

    df = df.dropna(subset=["place_key", "latitude", "longitude"])
    df = df[df["place_name"] != ""]
    df["place_key"] = df["place_key"].astype(int)
    df = df.drop_duplicates(subset=["place_key"], keep="first")

    split_names = df["place_name"].map(split_bilingual_name)
    df["place_name_gaelic"] = split_names.map(lambda x: x[0])
    df["place_name_english"] = split_names.map(lambda x: x[1])
    return df


def clean_people(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "Place number" not in df.columns:
        raise ValueError("people.csv is missing required column: 'Place number'")

    df["Place number"] = pd.to_numeric(df["Place number"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["Place number"])
    df["Place number"] = df["Place number"].astype(int)

    for col in df.columns:
        if col != "Place number":
            df[col] = df[col].map(cleaned_text)

    def gaelic_name(row: pd.Series) -> str:
        ainm = cleaned_text(row.get("Ainm", ""))
        cinneadh = cleaned_text(row.get("Cinneadh", ""))
        return " ".join(part for part in [ainm, cinneadh] if part).strip()

    def english_name(row: pd.Series) -> str:
        first = cleaned_text(row.get("Informant First Name", ""))
        last = cleaned_text(row.get("Informant Last Name", ""))
        return " ".join(part for part in [first, last] if part).strip()

    def display_name(row: pd.Series) -> str:
        gaelic = row["gaelic_name"]
        english = row["english_name"]
        if gaelic and english:
            return f"{gaelic} / {english}"
        return english or gaelic or cleaned_text(row.get("Informant ID", "")) or "Unnamed person"

    def sort_name(row: pd.Series) -> str:
        english_last = cleaned_text(row.get("Informant Last Name", ""))
        english_first = cleaned_text(row.get("Informant First Name", ""))
        cinneadh = cleaned_text(row.get("Cinneadh", ""))
        ainm = cleaned_text(row.get("Ainm", ""))

        candidate = " ".join(part for part in [english_last, english_first] if part).strip()
        if not candidate:
            candidate = " ".join(part for part in [cinneadh, ainm] if part).strip()
        if not candidate:
            candidate = cleaned_text(row.get("Informant ID", ""))

        return candidate.casefold()

    df["gaelic_name"] = df.apply(gaelic_name, axis=1)
    df["english_name"] = df.apply(english_name, axis=1)
    df["display_name"] = df.apply(display_name, axis=1)
    df["sort_name"] = df.apply(sort_name, axis=1)
    return df


def clean_communities(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    required = ["Community", "Traditions"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"communities.csv is missing required column(s): {missing}")

    df["Community"] = pd.to_numeric(df["Community"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["Community"])
    df["Community"] = df["Community"].astype(int)
    df["Tradition_keys"] = df["Traditions"].map(parse_number_list)
    return df


def clean_traditions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    required = ["Tradition", "Communities"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"traditions.csv is missing required column(s): {missing}")

    df["Tradition"] = pd.to_numeric(df["Tradition"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["Tradition"])
    df["Tradition"] = df["Tradition"].astype(int)
    df["Community_keys"] = df["Communities"].map(parse_number_list)
    return df


def build_people_lookup(people_df: pd.DataFrame) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}

    yob_yod_candidates = [
        "YoB-YoD",
        "Yob-Yod",
        "YOB-YOD",
        "YoB–YoD",
        "YOB–YOD",
        "YoB - YoD",
        "YOB - YOD",
        "Dates",
        "Date",
        "Years",
        "YoB/YoD",
    ]

    fallback_dates_col = people_df.columns[10] if len(people_df.columns) > 10 else None

    for place_key, group in people_df.sort_values(["sort_name", "display_name"]).groupby("Place number"):
        people_records: list[dict[str, str]] = []

        for _, row in group.iterrows():
            yob_yod = first_present_value(row, yob_yod_candidates)
            if not yob_yod and fallback_dates_col is not None:
                yob_yod = cleaned_text(row.get(fallback_dates_col, ""))

            people_records.append(
                {
                    "name": row["display_name"],
                    "sort_name": row["sort_name"],
                    "gaelic_name": cleaned_text(row.get("gaelic_name", "")),
                    "english_name": cleaned_text(row.get("english_name", "")),
                    "gaelic_first": cleaned_text(row.get("Ainm", "")),
                    "gaelic_last": cleaned_text(row.get("Cinneadh", "")) or cleaned_text(row.get("Cinneadh-breithe", "")) or cleaned_text(row.get("Sloinneadh", "")),
                    "id": cleaned_text(row.get("Informant ID", "")),
                    "yob_yod": yob_yod,
                    "sloinneadh": cleaned_text(row.get("Sloinneadh", "")),
                    "number_of_recordings": first_present_value(row, ["Number of Recordings", "Number of recordings"]),
                    "person_page_url": f"http://{BASE_URL}/cisc/informants/{cleaned_text(row.get('Informant ID', ''))}" if cleaned_text(row.get("Informant ID", "")) else "",
                    "recordings_url": f"http://{BASE_URL}/cisc/informants/{cleaned_text(row.get('Informant ID', ''))}#informant-recordings" if cleaned_text(row.get("Informant ID", "")) else "",
                }
            )

        result[str(int(place_key))] = people_records

    return result


def build_all_people_index(people_df: pd.DataFrame, places_df: pd.DataFrame) -> list[dict[str, str]]:
    place_lookup = {
        int(row.place_key): {
            "place_name": row.place_name,
            "place_name_gaelic": row.place_name_gaelic,
            "place_name_english": row.place_name_english,
            "latitude": float(row.latitude),
            "longitude": float(row.longitude),
        }
        for row in places_df.itertuples(index=False)
    }

    yob_yod_candidates = [
        "YoB-YoD",
        "Yob-Yod",
        "YOB-YOD",
        "YoB–YoD",
        "YOB–YOD",
        "YoB - YoD",
        "YOB - YOD",
        "Dates",
        "Date",
        "Years",
        "YoB/YoD",
    ]
    fallback_dates_col = people_df.columns[10] if len(people_df.columns) > 10 else None

    people_rows: list[dict[str, str]] = []

    for _, row in people_df.iterrows():
        place_key = int(row["Place number"])
        place = place_lookup.get(place_key)
        if not place:
            continue

        yob_yod = first_present_value(row, yob_yod_candidates)
        if not yob_yod and fallback_dates_col is not None:
            yob_yod = cleaned_text(row.get(fallback_dates_col, ""))

        english_last = cleaned_text(row.get("Informant Last Name", ""))
        english_first = cleaned_text(row.get("Informant First Name", ""))
        gaelic_first = cleaned_text(row.get("Ainm", ""))
        gaelic_last = cleaned_text(row.get("Cinneadh", "")) or cleaned_text(row.get("Cinneadh-breithe", "")) or cleaned_text(row.get("Sloinneadh", ""))
        gaelic_name = cleaned_text(row.get("gaelic_name", ""))
        english_name = cleaned_text(row.get("english_name", ""))
        display_name = cleaned_text(row.get("display_name", ""))
        initial = ((gaelic_last if gaelic_last else english_last)[:1] or display_name[:1] or "#").upper()
        if not initial.isalpha():
            initial = "#"

        people_rows.append(
            {
                "id": cleaned_text(row.get("Informant ID", "")),
                "display_name": display_name,
                "gaelic_name": gaelic_name,
                "english_name": english_name,
                "english_last": english_last,
                "english_first": english_first,
                "gaelic_last": gaelic_last,
                "gaelic_first": gaelic_first,
                "yob_yod": yob_yod,
                "sloinneadh": cleaned_text(row.get("Sloinneadh", "")),
                "letter": initial,
                "sort_key": f"{english_last.casefold()}|{english_first.casefold()}|{display_name.casefold()}",
                "place_key": str(place_key),
                "place_name": place["place_name"],
                "place_name_gaelic": place["place_name_gaelic"],
                "place_name_english": place["place_name_english"],
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "number_of_recordings": first_present_value(row, ["Number of Recordings", "Number of recordings"]),
                "person_page_url": f"http://{BASE_URL}/cisc/informants/{cleaned_text(row.get('Informant ID', ''))}" if cleaned_text(row.get("Informant ID", "")) else "",
                "recordings_url": f"http://{BASE_URL}/cisc/informants/{cleaned_text(row.get('Informant ID', ''))}#informant-recordings" if cleaned_text(row.get("Informant ID", "")) else "",
            }
        )

    people_rows.sort(key=lambda p: (p["letter"], p["sort_key"]))
    return people_rows


def build_community_tradition_lookup(
        communities_df: pd.DataFrame,
        traditions_df: pd.DataFrame,
        all_places_df: pd.DataFrame,
) -> dict[str, list[dict[str, str]]]:
    place_lookup = {
        int(row.place_key): {
            "gaelic": row.place_name_gaelic,
            "english": row.place_name_english,
            "plain": format_bilingual_plain(row.place_name_gaelic, row.place_name_english),
        }
        for row in all_places_df.itertuples(index=False)
    }

    tradition_colour_lookup = {
        int(row.Tradition): TRADITION_COLOURS[idx % len(TRADITION_COLOURS)]
        for idx, row in enumerate(traditions_df.itertuples(index=False))
    }

    result: dict[str, list[dict[str, str]]] = {}

    for row in communities_df.itertuples(index=False):
        items: list[dict[str, str]] = []
        for key in row.Tradition_keys:
            place = place_lookup.get(key)
            if not place:
                continue
            items.append(
                {
                    "key": str(key),
                    "gaelic": place["gaelic"],
                    "english": place["english"],
                    "plain": place["plain"],
                    "colour": tradition_colour_lookup.get(key, ACCENT),
                }
            )

        items = sorted(items, key=lambda x: x["plain"].casefold())
        result[str(int(row.Community))] = items

    return result


def build_tradition_overlay_specs(
        traditions_df: pd.DataFrame,
        all_places_df: pd.DataFrame,
        cape_breton_places_df: pd.DataFrame,
        people_counts_lookup: dict[int, int],
) -> list[dict[str, Any]]:
    all_places_by_key = {int(row.place_key): row for row in all_places_df.itertuples(index=False)}
    cb_places_by_key = {int(row.place_key): row for row in cape_breton_places_df.itertuples(index=False)}

    specs: list[dict[str, Any]] = []

    for idx, row in enumerate(traditions_df.itertuples(index=False)):
        tradition_key = int(row.Tradition)
        tradition_place = all_places_by_key.get(tradition_key)
        if not tradition_place:
            continue

        points = []
        cb_place_names = []
        for community_key in row.Community_keys:
            place = cb_places_by_key.get(community_key)
            if not place:
                continue
            points.append(
                {
                    "place_key": community_key,
                    "place_name": place.place_name,
                    "gaelic": place.place_name_gaelic,
                    "english": place.place_name_english,
                    "latitude": float(place.latitude),
                    "longitude": float(place.longitude),
                    "people_count": int(people_counts_lookup.get(community_key, 0)),
                }
            )
            cb_place_names.append(format_bilingual_plain(place.place_name_gaelic, place.place_name_english))

        cb_place_names_sorted = sorted(cb_place_names, key=lambda s: s.casefold())
        cb_places_hover = "<br>".join(
            cb_place_names_sorted) if cb_place_names_sorted else "No linked Cape Breton places"

        tradition_label_plain = format_bilingual_plain(
            tradition_place.place_name_gaelic,
            tradition_place.place_name_english,
        )

        specs.append(
            {
                "trace_index_offset": idx,
                "tradition_key": tradition_key,
                "label_plain": tradition_label_plain,
                "label_gaelic": tradition_place.place_name_gaelic,
                "label_english": tradition_place.place_name_english,
                "colour": TRADITION_COLOURS[idx % len(TRADITION_COLOURS)],
                "community_points": points,
                "community_place_names": cb_place_names_sorted,
                "community_places_hover": cb_places_hover,
                "scotland_point": {
                    "place_key": tradition_key,
                    "place_name": tradition_place.place_name,
                    "gaelic": tradition_place.place_name_gaelic,
                    "english": tradition_place.place_name_english,
                    "latitude": float(tradition_place.latitude),
                    "longitude": float(tradition_place.longitude),
                },
            }
        )

    return specs


def make_main_figure(places_df: pd.DataFrame, tradition_specs: list[dict[str, Any]]) -> go.Figure:
    counts = places_df["people_count"].fillna(0).astype(float)
    sizes = np.where(counts > 0, 10 + np.sqrt(counts) * 5, 8)

    max_count = float(counts.max()) if len(counts) else 0.0
    if max_count > 0:
        opacity = 0.52 + 0.38 * (counts / max_count)
    else:
        opacity = np.full(len(counts), 0.60)

    fig = go.Figure()

    fig.add_trace(
        go.Scattermap(
            lat=places_df["latitude"],
            lon=places_df["longitude"],
            mode="markers",
            marker={
                "size": sizes,
                "opacity": opacity,
                "color": counts,
                "colorscale": [
                    [0.0, "#90C3E6"],
                    [0.35, "#4E9DD2"],
                    [0.65, "#2F7FBF"],
                    [1.0, "#1F5F99"],
                ],
                "showscale": False,
            },
            customdata=list(
                zip(
                    places_df["place_key"],
                    places_df["place_name"],
                    places_df["people_count"],
                    strict=False,
                )
            ),
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "Informants: %{customdata[2]}<extra></extra>"
            ),
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scattermap(
            lat=[],
            lon=[],
            mode="markers",
            marker={"size": 30, "color": ACCENT, "opacity": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scattermap(
            lat=[],
            lon=[],
            mode="markers",
            marker={"size": 14, "color": "#ffffff", "opacity": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )

    for spec in tradition_specs:
        points = spec["community_points"]
        fig.add_trace(
            go.Scattermap(
                lat=[p["latitude"] for p in points],
                lon=[p["longitude"] for p in points],
                mode="markers",
                visible=False,
                marker={"size": 16, "opacity": 1, "color": spec["colour"]},
                customdata=[
                    [p["place_key"], p["place_name"], p["people_count"], spec["label_plain"]]
                    for p in points
                ],
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "Tradition: %{customdata[3]}<br>"
                    "Informants: %{customdata[2]}<extra></extra>"
                ),
                showlegend=False,
            )
        )

    fig.update_layout(
        map={"style": "carto-positron", "center": MAP_CENTER, "zoom": MAP_ZOOM},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=760,
        showlegend=False,
    )
    return fig


def make_inset_figure(tradition_specs: list[dict[str, Any]]) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(
        go.Scattermap(
            lat=[],
            lon=[],
            mode="markers",
            marker={"size": 28, "color": ACCENT, "opacity": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scattermap(
            lat=[],
            lon=[],
            mode="markers",
            marker={"size": 12, "color": "#ffffff", "opacity": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )

    for spec in tradition_specs:
        point = spec["scotland_point"]
        fig.add_trace(
            go.Scattermap(
                lat=[point["latitude"]],
                lon=[point["longitude"]],
                mode="markers",
                visible=False,
                marker={
                    "size": 16,
                    "opacity": 1,
                    "color": spec["colour"],
                },
                customdata=[
                    [
                        point["place_key"],
                        point["place_name"],
                        spec["community_places_hover"],
                    ]
                ],
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br><br>"
                    "Associated with:<br><br>%{customdata[2]}<extra></extra>"
                ),
                showlegend=False,
            )
        )

    fig.update_layout(
        map={
            "style": "carto-positron",
            "center": {"lat": SCOTLAND_CENTER["lat"], "lon": SCOTLAND_CENTER["lon"]},
            "zoom": float(SCOTLAND_ZOOM),
            "domain": {"x": [0.0, 1.0], "y": [0.0, 1.0]},
        },
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        showlegend=False,
        hoverlabel={"font": {"size": 10}},
    )
    return fig


def render_html(
        main_fig: go.Figure,
        inset_fig: go.Figure,
        places_df: pd.DataFrame,
        people_lookup: dict[str, list[dict[str, str]]],
        all_people_index: list[dict[str, str]],
        community_traditions_lookup: dict[str, list[dict[str, str]]],
        tradition_specs: list[dict[str, Any]],
        output_path: Path,
) -> None:
    main_fig_dict = main_fig.to_dict()
    inset_fig_dict = inset_fig.to_dict()
    plotly_js = get_plotlyjs()

    places_lookup = {
        str(int(row.place_key)): {
            "place_name": row.place_name,
            "place_name_gaelic": row.place_name_gaelic,
            "place_name_english": row.place_name_english,
            "people_count": int(row.people_count),
            "latitude": float(row.latitude),
            "longitude": float(row.longitude),
            "traditions": community_traditions_lookup.get(str(int(row.place_key)), []),
        }
        for row in places_df.itertuples(index=False)
    }

    overlay_controls_all = [
        {
            "main_trace_index": 3 + idx,
            "inset_trace_index": 2 + idx,
            "tradition_key": spec["tradition_key"],
            "label_plain": spec["label_plain"],
            "label_gaelic": spec["label_gaelic"],
            "label_english": spec["label_english"],
            "colour": spec["colour"],
        }
        for idx, spec in enumerate(tradition_specs)
    ]
    map_controls_svg_path = Path(__file__).resolve().parent / "map_controls.svg"
    if map_controls_svg_path.exists():
        map_controls_svg = map_controls_svg_path.read_text(encoding="utf-8")
    else:
        map_controls_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 180"><rect width="300" height="180" rx="14" fill="white" stroke="#8CC7EA"/><text x="150" y="92" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#1F5F99">Map controls graphic not found</text></svg>'''

    place_keys_sorted = [
        str(int(row.place_key))
        for row in places_df.sort_values(
            by=["place_name", "place_name_gaelic", "place_name_english"],
            key=lambda s: s.fillna("").astype(str).str.casefold() if hasattr(s, 'fillna') else s,
        ).itertuples(index=False)
    ]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cainnt is Ceathramhan | Language and Lyrics</title>
<script type="text/javascript">
{plotly_js}
</script>
<style>
    html, body {{
        margin: 0;
        padding: 0;
        height: 100%;
        overflow: hidden;
        font-family: "Cooper Hewitt", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-style: normal;
        font-weight: 400;
        font-size: 18px;
        line-height: 33.75px;
        color: {BODY_TEXT};
        background: {PANEL_BG};
    }}

    :root {{
        --floating-panel-width: min(19%, 280px);
        --floating-panel-min-width: 220px;
        --floating-panel-height: 42%;
    }}

    .page {{
        display: flex;
        flex-direction: column;
        height: 100vh;
        overflow: hidden;
    }}
    
    /* ---------------------------
       Banner / Header Layout
    --------------------------- */
    
    .banner {{
        flex: 0 0 {BANNER_HEIGHT}px;
        box-sizing: border-box;
        padding: 14px 28px 12px 28px;
        background: {BANNER_BG};
        border-bottom: 1px solid rgba(255, 255, 255, 0.18);
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 6px;
    }}
    
    .banner h1,
    .banner .subheading {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        align-items: center;
        margin: 0;
        position: relative;
    }}
    
    .banner {{
        flex: 0 0 {BANNER_HEIGHT}px;
        box-sizing: border-box;
        padding: 14px 28px 12px 28px;
        background: {BANNER_BG};
        border-bottom: 1px solid rgba(255, 255, 255, 0.18);
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 6px;
        position: relative;
    }}
    
    /* central vertical divider */
    .banner::after {{
        content: "";
        position: absolute;
        left: 50%;
        top: 20%;
        bottom: 20%;
        width: 2px;
        background: {ACCENT};
        transform: translateX(-50%);
        opacity: 0.95;
    }}
    
    .banner h1 {{
        font-size: 48px;
        font-weight: 700;
        color: {BANNER_GAELIC};
        line-height: 48px;
        text-transform: uppercase;
    }}
    
    .banner .subheading {{
        font-size: 25.2px;
        font-weight: 700;
        color: {BANNER_GAELIC};
        line-height: 28.8px;
        text-transform: uppercase;
    }}
    
    .banner .gaelic-banner,
    .banner .english-highlight-banner {{
        display: block;
        white-space: nowrap;
    }}
    
    .banner .gaelic-banner {{
        text-align: right;
        padding-right: 18px;
        color: {BANNER_GAELIC};
    }}
    
    .banner .english-highlight-banner {{
        text-align: left;
        padding-left: 18px;
        color: {ACCENT};
    }}
    
    .banner h1 .english-highlight-banner {{
        font-size: 33.6px;
        line-height: 33.6px;
    }}
    
    .banner .subheading .english-highlight-banner {{
        font-size: 17.64px;
        line-height: 20.16px;
    }}
    

    .content {{
        display: flex;
        flex: 1 1 auto;
        min-height: 0;
        overflow: hidden;
    }}
    
    .side-panel {{
        flex: 0 0 clamp(500px, 26vw, 560px);
        max-width: clamp(500px, 26vw, 560px);
        min-width: 500px;
        box-sizing: border-box;
        padding: 18px;
        overflow: hidden;
        background: {PANEL_BG};
        border-right: 1px solid rgba(25, 41, 48, 0.08);
        display: flex;
        flex-direction: column;
        gap: 10px;
    }}
    
    .recordings-meta-block {{
        width: 100%;
    }}
    
    .recordings-meta-row {{
        display: flex;
        align-items: center;
        gap: 12px;
        width: 100%;
    }}
    
    .recordings-meta-left {{
        display: flex;
        align-items: baseline;
        gap: 8px;
        min-width: 0;
        flex-wrap: wrap;
    }}
    
    .recordings-link-btn {{
        margin-left: auto;
        flex-shrink: 0;
    }}
    
    .person-page-link-btn,
    .recordings-link-btn {{
        display: inline-block;
        padding: 8px 12px;
        border: 1px solid rgba(25, 41, 48, 0.15);
        border-radius: 999px;
        background: #ffffff;
        color: {TITLE_COLOUR};
        text-decoration: none;
        font-size: 12px;
        font-weight: 700;
        line-height: 1.2;
        white-space: nowrap;
    }}
    
    .person-page-link-btn:hover,
    .recordings-link-btn:hover {{
        border-color: {ACCENT};
        color: {ACCENT};
    }}
    
    .side-panel-mode-toggle {{
        display: flex;
        gap: 6px;
        margin-bottom: 0;
        flex-wrap: nowrap;
        align-items: flex-end;
        position: relative;
        z-index: 3;
    }}
    
    details.person-card.selected {{
        border-left: 6px solid {TITLE_COLOUR};
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(25, 41, 48, 0.08);
    }}
    
    details.person-card.selected > summary {{
        background: rgba(31, 95, 153, 0.08);
        color: {TITLE_COLOUR};
    }}
    
    details.person-card.selected .english-highlight-person {{
        color: {ACCENT};
    }}
    
    details.person-card.selected > summary::after {{
        color: {ACCENT};
    }}
    
    details.person-card.selected .separator-accent {{
        color: {ACCENT};
    }}

    .mode-btn {{
        position: relative;
        flex: 1 1 50%;
        width: 50%;
        padding: 12px 14px 11px 14px;
        border: 1px solid rgba(25, 41, 48, 0.15);
        border-bottom: 1px solid rgba(25, 41, 48, 0.12);
        background: #f4f8fb;
        color: {BODY_TEXT};
        font-size: 15px;
        font-weight: 700;
        text-transform: none;
        text-align: center;
        cursor: pointer;
        border-radius: 8px 8px 0 0;
        box-shadow: none;
        margin-bottom: -1px;
        line-height: 1.2;
    }}
    
    .mode-btn.active {{
        background: #ffffff;
        color: {TITLE_COLOUR};
        border-color: rgba(25, 41, 48, 0.12);
        border-bottom-color: #ffffff;
        box-shadow: none;
        z-index: 4;
    }}

    .mode-btn .gaelic-dark {{
        color: {TITLE_COLOUR};
    }}
    
    .mode-btn .english-accent {{
        color: {ACCENT};
    }}
    
    .mode-btn .separator-accent {{
        color: {ACCENT};
    }}
    
    .mode-btn.active .gaelic-dark {{
        color: {TITLE_COLOUR};
    }}
    
    .mode-btn.active .english-accent {{
        color: {ACCENT};
    }}
    
    .mode-btn.active .separator-accent {{
        color: {ACCENT};
    }}

    .mode-btn .gaelic-dark,
    .mode-btn .english-accent,
    .mode-btn .separator-accent {{
        font-weight: 700;
        white-space: nowrap;
        font-size: 19px;
        line-height: 1.2;
    }}

    .panel-view {{
        display: none;
        flex: 1 1 auto;
        min-height: 0;
        overflow: hidden;
        flex-direction: column;
        background: #ffffff;
        border: 1px solid rgba(25, 41, 48, 0.12);
        border-radius: 0 8px 8px 8px;
        padding: 14px 14px 12px 14px;
        box-sizing: border-box;
    }}

    .panel-view.active {{
        display: flex;
    }}
    
    .informants-pane {{
        flex: 1 1 auto;
        min-height: 0;
        overflow-y: auto;
        padding-right: 4px;
        display: flex;
        flex-direction: column;
    }}


    .places-index-wrap {{
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
    }}

    .places-index-title {{
        display: none;
    }}

    .places-index-controls {{
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 7px;
        margin: 0 0 10px 0;
        padding: 0 4px 0 2px;
        font-size: 12px;
        line-height: 16px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: rgba(25, 41, 48, 0.72);
    }}

    .places-index-wrap .info-header {{
        flex: 0 0 auto;
    }}

    .places-index-wrap .location-intro,
    #all-people-panel-view .people-intro {{
        margin: 4px auto 14px auto;
        max-width: 430px;
    }}

    .place-sort-label {{
        color: rgba(25, 41, 48, 0.68);
        font-weight: 700;
    }}

    .place-sort-btn {{
        appearance: none;
        border: none;
        background: transparent;
        padding: 1px 0;
        margin: 0;
        cursor: pointer;
        font: inherit;
        font-weight: 600;
        line-height: inherit;
        border-bottom: 1px solid transparent;
        transition: color 0.14s ease, border-color 0.14s ease, opacity 0.14s ease;
    }}

    .place-sort-btn.sort-gd {{
        color: {TITLE_COLOUR};
    }}

    .place-sort-btn.sort-en {{
        color: {ACCENT};
    }}

    .place-sort-btn:hover {{
        opacity: 0.84;
    }}

    .place-sort-btn.active {{
        font-weight: 700;
        border-bottom-color: {ACCENT};
        opacity: 1;
    }}

    .place-sort-btn:not(.active) {{
        font-weight: 600;
        opacity: 0.94;
    }}

    .place-sort-separator {{
        color: {ACCENT};
        font-weight: 700;
    }}

    .places-index-list {{
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
        gap: 6px;
        overflow-y: auto;
        padding-right: 2px;
    }}

    .place-list-btn {{
        width: 100%;
        text-align: left;
        padding: 8px 10px;
        border: 1px solid rgba(25, 41, 48, 0.10);
        border-left: 4px solid rgba(31, 95, 153, 0.18);
        border-radius: 6px;
        background: #fff;
        cursor: pointer;
        font: inherit;
        line-height: 1.25;
        color: {BODY_TEXT};
        transition: border-color 0.14s ease, box-shadow 0.14s ease, transform 0.14s ease, background-color 0.14s ease;
    }}

    .place-list-btn:hover {{
        border-color: {ACCENT};
    }}

    .place-list-btn.active {{
        border-left-color: {TITLE_COLOUR};
        background: rgba(31, 95, 153, 0.06);
        box-shadow: 0 2px 8px rgba(25, 41, 48, 0.08);
        transform: translateY(-1px);
        animation: placeSelectPulse 0.18s ease-out;
    }}

    @keyframes placeSelectPulse {{
        0% {{
            transform: translateY(0);
            box-shadow: 0 1px 2px rgba(25, 41, 48, 0.03);
        }}
        100% {{
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(25, 41, 48, 0.08);
        }}
    }}

    .place-list-name {{
        display: block;
        font-size: 14px;
        line-height: 18px;
        font-weight: 700;
    }}

    .place-list-detail {{
        margin-top: 6px;
        padding: 4px 0 2px 0;
        animation: placeDetailReveal 0.18s ease-out;
        transform-origin: top center;
    }}

    @keyframes placeDetailReveal {{
        0% {{
            opacity: 0;
            transform: translateY(-4px);
        }}
        100% {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    .place-list-detail .place-meta {{
        display: none;
    }}

    .place-list-detail .informants-pane {{
        margin-top: 4px;
        padding: 10px 12px 2px 12px;
        border: 1px solid rgba(25, 41, 48, 0.06);
        border-radius: 6px;
        background: #f7fbfe;
        box-shadow: none;
        overflow: visible;
    }}

    .place-list-detail .informants-pane .empty {{
        margin-top: 0;
    }}

    .place-list-meta {{
        display: block;
        margin-top: 3px;
        font-size: 11px;
        line-height: 14px;
        color: rgba(25, 41, 48, 0.72);
        text-transform: uppercase;
    }}

    .place-list-item {{
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(25, 41, 48, 0.06);
    }}

    .place-list-item:last-child {{
        border-bottom: none;
    }}

    .associated-pane .overlay-empty {{
        padding-top: 8px;
    }}
    
    .location-lower-panel {{
        flex: 0 0 22vh;
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-top: 8px;
        min-height: 0;
    }}
    
    
    .location-traditions-toggle-wrap {{
        display: none !important;
    }}
    
    #location-traditions-toggle-btn {{
        display: none !important;
    }}
    
    .associated-pane {{
        flex: 1 1 auto;
        min-height: 0;
        max-height: none;
        overflow-y: auto;
        padding-top: 4px;
        padding-right: 4px;
        border-top: 1px solid rgba(25, 41, 48, 0.08);
        box-sizing: border-box;
    }}

    .map-panel {{
        position: relative;
        flex: 1 1 auto;
        min-width: 0;
        background: #fff;
        overflow: hidden;
    }}

    #map {{
        width: 100%;
        height: 100%;
    }}

    .map-reset-btn {{
        position: static;
        padding: 8px 12px;
        border: 1px solid rgba(25, 41, 48, 0.15);
        background: #ffffff;
        color: {BODY_TEXT};
        font-size: 14px;
        font-weight: 700;
        text-transform: uppercase;
        cursor: pointer;
        border-radius: 4px;
    }}

    .map-reset-btn:hover,
    .mode-btn:hover {{
        border-color: {ACCENT};
        color: {ACCENT};
    }}

    .top-map-buttons {{
        position: absolute;
        top: 12px;
        left: 12px;
        z-index: 1001;
        display: flex;
        gap: 8px;
    }}

    .overlay-toggle-btn,
    .inset-toggle-btn {{
        display: none !important;
    }}

    .floating-panel {{
        position: absolute;
        z-index: 1002;
        width: var(--floating-panel-width);
        min-width: var(--floating-panel-min-width);
        height: var(--floating-panel-height);
        overflow: hidden;
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid rgba(25, 41, 48, 0.10);
        border-left: 4px solid {ACCENT};
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.10);
        display: flex;
        flex-direction: column;
        backdrop-filter: blur(2px);
    }}

    .floating-panel.hidden {{
        display: none;
    }}

    .floating-panel-header {{
        flex: 0 0 auto;
        padding: 10px 12px 0 12px;
    }}

    .floating-panel-body {{
        flex: 1 1 auto;
        min-height: 0;
        overflow: hidden;
        padding: 8px 12px 10px 12px;
        display: flex;
        flex-direction: column;
    }}

    .floating-overlays {{
        right: 16px;
        top: 48px;
        bottom: 56px;
        height: auto;
        width: min(22%, 320px);
    }}

    .floating-inset {{
        display: none !important;
    }}

    .combined-traditions-body {{
        gap: 12px;
    }}

    .combined-inset-block {{
        position: relative;
        flex: 0 0 43%;
        min-height: 220px;
        display: flex;
        flex-direction: column;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(25, 41, 48, 0.08);
    }}

    .combined-controls-block {{
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
    }}

    .combined-controls-block .overlay-list {{
        flex: 1 1 auto;
        min-height: 0;
    }}

    .floating-panel .section-title {{
        font-size: 12px;
        line-height: 16px;
        margin: 0 0 6px 0;
    }}

    .floating-panel .intro {{
        font-size: 13px;
        line-height: 18px;
        margin: 0 0 8px 0;
    }}

    #inset-map {{
        width: 100%;
        height: 100%;
        min-height: 0;
    }}

    .inset-selected-place-label {{
        position: absolute;
        z-index: 1004;
        display: none;
        pointer-events: none;
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid rgba(95, 167, 214, 0.45);
        border-radius: 6px;
        padding: 4px 8px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        white-space: nowrap;
        transform: translate(10px, -50%);
        max-width: 240px;
        font-size: 11px;
        line-height: 14px;
    }}

    .inset-selected-place-label .gaelic {{
        color: {TITLE_COLOUR};
        font-size: 11px;
        font-weight: 700;
        line-height: 14px;
    }}

    .inset-selected-place-label .english {{
        color: {ACCENT};
        font-size: 11px;
        font-weight: 700;
        line-height: 14px;
    }}

    .inset-selected-place-label .separator {{
        color: {ACCENT};
        font-size: 11px;
        font-weight: 700;
        line-height: 14px;
        margin: 0 0.15em;
    }}

    .filters-controls,
    .people-list-controls {{
        display: flex;
        gap: 6px;
        margin-bottom: 8px;
        flex-wrap: wrap;
    }}

    .people-index-controls {{
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 7px;
        margin: 0 0 10px 0;
        padding: 0 4px 0 2px;
        font-size: 12px;
        line-height: 16px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: rgba(25, 41, 48, 0.72);
    }}

    .tiny-btn {{
        padding: 4px 8px;
        border: 1px solid rgba(25, 41, 48, 0.15);
        background: #ffffff;
        color: {BODY_TEXT};
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        cursor: pointer;
        border-radius: 4px;
    }}

    .tiny-btn:hover {{
        border-color: {ACCENT};
        color: {ACCENT};
    }}

    .overlay-list {{
        display: grid;
        gap: 6px;
        align-content: start;
        grid-auto-rows: max-content;
        overflow-y: auto;
        padding-right: 2px;
        font-size: 13px;
        line-height: 1.25;
    }}

    .people-list {{
        display: block;
        overflow-y: auto;
        padding-right: 2px;
        font-size: 13px;
        line-height: 1.25;
    }}
        
    .people-letter-group {{
        border-top: 1px solid rgba(25, 41, 48, 0.08);
        margin-top: 6px;
        padding-top: 4px;
    }}
    
    .people-letter-group summary {{
        cursor: pointer;
        list-style: none;
        font-size: 14px;
        font-weight: 700;
        color: #1F5F99;
        text-transform: uppercase;
        line-height: 18px;
        padding: 2px 0 6px 0;
    }}
    
    .people-letter-group summary::-webkit-details-marker {{
        display: none;
    }}
    
    .people-letter-group > summary::after {{
        content: '+';
        float: right;
        color: #8CC7EA;
        font-size: 0.95rem;
        font-weight: 700;
    }}
    
    .people-letter-group[open] > summary::after {{
        content: '–';
    }}
    
    .people-letter-group-body {{
        padding-top: 2px;
    }}
    .overlay-row {{
        display: flex;
        align-items: flex-start;
        gap: 8px;
        line-height: 1.25;
    }}

    .overlay-row input {{
        margin-top: 2px;
        transform: scale(0.95);
    }}

    .colour-chip {{
        width: 10px;
        height: 10px;
        border-radius: 999px;
        margin-top: 3px;
        flex: 0 0 10px;
        border: 1px solid rgba(0, 0, 0, 0.08);
    }}

    .overlay-label {{
        flex: 1 1 auto;
        min-width: 0;
        word-break: break-word;
    }}

    .overlay-empty,
    .people-empty {{
        color: {BODY_TEXT};
        font-size: 12px;
        line-height: 16px;
        opacity: 0.75;
    }}

    .selected-place-label {{
        position: absolute;
        z-index: 1002;
        display: none;
        pointer-events: none;
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid rgba(95, 167, 214, 0.45);
        border-radius: 6px;
        padding: 6px 10px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        white-space: nowrap;
        transform: translate(16px, -50%);
        max-width: 380px;
    }}

    .selected-place-label .gaelic {{
        color: {TITLE_COLOUR};
        font-size: 16px;
        font-weight: 700;
        line-height: 22px;
    }}

    .selected-place-label .english {{
        color: {ACCENT};
        font-size: 16px;
        font-weight: 700;
        line-height: 22px;
    }}

    .selected-place-label .separator {{
        color: {ACCENT};
        font-size: 16px;
        font-weight: 700;
        line-height: 22px;
        margin: 0 0.2em;
    }}

    .section-title {{
        font-size: 13px;
        font-weight: 700;
        color: {ACCENT};
        line-height: 18px;
        text-transform: uppercase;
        margin: 0 0 6px 0;
    }}

    .intro {{
        margin: 0 0 4px 0;
        font-size: 13px;
        line-height: 18px;
    }}

    .location-intro,
    .people-intro {{
        margin: 4px auto 16px auto;
        text-align: center;
        max-width: 420px;
        font-size: 14px;
        line-height: 20px;
        color: rgba(25, 41, 48, 0.75);
    }}

    .location-intro::after,
    .people-intro::after {{
        content: "";
        display: block;
        width: 48px;
        height: 1px;
        background: rgba(25, 41, 48, 0.10);
        margin: 10px auto 0 auto;
    }}

    .gaelic-dark {{
        color: {TITLE_COLOUR};
    }}

    .english-accent {{
        color: {ACCENT};
    }}

    .place-title {{
        font-size: 20px;
        font-weight: 700;
        color: {TITLE_COLOUR};
        line-height: 24px;
        margin: 0 0 4px 0;
    }}

    .place-meta {{
        font-size: 13px;
        line-height: 18px;
        color: {BODY_TEXT};
        margin-bottom: 8px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(25, 41, 48, 0.08);
    }}

    .info-header {{
        flex: 0 0 auto;
    }}

    .associated-box {{
        background: #f5f9fc;
        border-left: 4px solid {ACCENT};
        border-radius: 6px;
        padding: 8px 10px;
        margin-bottom: 12px;
    }}

    .associated-list {{
        list-style: none;
        margin: 0;
        padding: 0;
        line-height: 1.35;
    }}

    .associated-list li {{
        margin: 0 0 6px 0;
        display: flex;
        align-items: flex-start;
        gap: 8px;
        font-size: 13px;
        line-height: 17px;
    }}

    .associated-bullet {{
        width: 10px;
        height: 10px;
        border-radius: 999px;
        margin-top: 3px;
        flex: 0 0 10px;
        border: 1px solid rgba(0, 0, 0, 0.08);
    }}

    .person-card {{
        background: {CARD_BG};
        border: 1px solid rgba(25, 41, 48, 0.08);
        border-left: 4px solid {ACCENT};
        border-radius: 6px;
        margin-bottom: 10px;
        overflow: hidden;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
        transition: border-color 0.14s ease, box-shadow 0.14s ease, transform 0.14s ease;
    }}

    details.person-card summary {{
        cursor: pointer;
        padding: 10px 12px;
        list-style: none;
        color: {BODY_TEXT};
        background: #fff;
        font-size: 14px;
        line-height: 19px;
        transition: background-color 0.14s ease, color 0.14s ease;
    }}
    
    details.person-card summary {{
        text-transform: none;
    }}

    details.person-card summary::-webkit-details-marker {{
        display: none;
    }}

    details.person-card > summary::after {{
        content: '+';
        float: right;
        color: {ACCENT};
        font-size: 0.95rem;
        margin-left: 1rem;
        font-weight: 700;
        transition: color 0.14s ease;
    }}
    
    details.person-card[open] > summary::after {{
        content: '–';
    }}
    
    details.person-card > summary .person-summary-name {{
        font-weight: 700;
    }}
    
    .metadata {{
        padding: 10px 12px 12px 12px;
        border-top: 1px solid rgba(25, 41, 48, 0.06);
        background: #f7fbfe;
    }}

    .meta-block {{
        margin-bottom: 8px;
    }}

    .meta-line {{
        display: flex;
        gap: 16px;
        margin-bottom: 8px;
        flex-wrap: wrap;
        align-items: flex-start;
    }}
    
    .meta-line-col {{
        min-width: 0;
        flex: 0 1 auto;
    }}
    
    .meta-line-top .meta-line-col {{
        min-width: 90px;
    }}
    
    .meta-line-col-button {{
        margin-left: auto;
        flex: 0 0 auto;
    }}

    .meta-label {{
        font-size: 12px;
        font-weight: 700;
        color: {ACCENT};
        line-height: 16px;
        text-transform: uppercase;
        margin-bottom: 1px;
    }}

    .meta-value,
    .meta-inline-value {{
        color: {BODY_TEXT};
        word-break: break-word;
        font-size: 13px;
        line-height: 17px;
    }}
    
    .meta-top-row {{
        display: flex;
        align-items: flex-start;
        gap: 16px;
        margin-bottom: 10px;
        width: 100%;
    }}
    
    .meta-top-item {{
        min-width: 0;
        flex: 0 0 110px;
    }}
    
    .meta-top-item-button {{
        margin-left: auto;
        flex: 0 0 auto;
    }}
    
    .person-page-link-btn,
    .recordings-link-btn {{
        display: inline-block;
        padding: 8px 12px;
        border: 1px solid rgba(25, 41, 48, 0.15);
        border-radius: 999px;
        background: #ffffff;
        color: {TITLE_COLOUR};
        text-decoration: none;
        font-size: 12px;
        font-weight: 700;
        line-height: 1.2;
        white-space: nowrap;
    }}
    
    .person-page-link-btn:hover,
    .recordings-link-btn:hover {{
        border-color: {ACCENT};
        color: {ACCENT};
    }}

    .empty {{
        color: {BODY_TEXT};
        background: #fff;
        border: 1px dashed rgba(25, 41, 48, 0.12);
        border-left: 4px solid {ACCENT};
        border-radius: 6px;
        padding: 12px;
        font-size: 13px;
        line-height: 17px;
    }}

    .location-empty-state {{
        position: relative;
        flex: 1 1 auto;
        min-height: 0;
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
        padding: 18px;
        background: linear-gradient(
            to bottom,
            rgba(255, 255, 255, 0.92),
            rgba(247, 251, 254, 0.92)
        );
        border: 1px dashed rgba(25, 41, 48, 0.12);
        border-left: 4px solid rgba(140, 199, 234, 0.95);
        border-radius: 6px;
        color: rgba(25, 41, 48, 0.82);
        text-align: center;
    }}

    .location-empty-message {{
        position: relative;
        z-index: 1;
        display: inline-block;
        max-width: 280px;
        color: {TITLE_COLOUR};
        font-size: 16px;
        line-height: 22px;
        font-weight: 700;
    }}

    .location-empty-state::before {{
        content: "";
        position: absolute;
        inset: 12px;
        border: 1px dashed rgba(25, 41, 48, 0.05);
        border-radius: 4px;
        pointer-events: none;
    }}

    .english-highlight-place {{
        color: {ACCENT};
    }}

    .english-highlight-person {{
        color: {ACCENT};
        font-style: italic;
    }}

    .person-summary-name {{
        display: inline;
        color: {TITLE_COLOUR};
    }}

    .people-letter-heading {{
        margin: 6px 0 2px 0;
        padding-top: 4px;
        border-top: 1px solid rgba(25, 41, 48, 0.08);
        font-size: 14px;
        font-weight: 700;
        color: {TITLE_COLOUR};
        text-transform: uppercase;
    }}

    .people-jump-btn {{
        width: 100%;
        text-align: left;
        padding: 8px 10px;
        border: 1px solid rgba(25, 41, 48, 0.10);
        border-radius: 4px;
        background: #fff;
        cursor: pointer;
        font: inherit;
        color: {BODY_TEXT};
    }}

    .people-jump-btn:hover {{
        border-color: {ACCENT};
    }}

    .people-name-line {{
        font-size: 14px;
        line-height: 18px;
        margin-bottom: 4px;
    }}

    .people-place-line {{
        font-size: 12px;
        line-height: 16px;
    }}

    .map-panel .modebar-container {{
        position: absolute !important;
        top: 12px !important;
        right: 12px !important;
        left: auto !important;
        width: auto !important;
        pointer-events: none;
        z-index: 1000 !important;
    }}

    .map-panel .modebar {{
        position: static !important;
        pointer-events: auto;
        margin: 0 !important;
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid rgba(25, 41, 48, 0.12);
        border-radius: 4px;
        padding: 2px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
    }}

    #inset-map .mapboxgl-ctrl-bottom-right,
    #inset-map .maplibregl-ctrl-bottom-right {{
        display: none !important;
    }}

    /* Main map attribution/info control: move to bottom-left and keep visible */
    #map .mapboxgl-ctrl-bottom-right,
    #map .maplibregl-ctrl-bottom-right {{
        left: 28px !important;
        right: auto !important;
        bottom: 28px !important;
    }}
    
    #map .mapboxgl-ctrl-bottom-right .mapboxgl-ctrl,
    #map .maplibregl-ctrl-bottom-right .maplibregl-ctrl {{
        margin: 0 !important;
        padding: 0 !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }}
    
    #map .mapboxgl-ctrl-attrib,
    #map .maplibregl-ctrl-attrib {{
        position: relative;
        overflow: visible !important;
        margin: 0 !important;
        padding: 0 !important;
        width: 22px !important;
        min-width: 22px !important;
        height: 22px !important;
        min-height: 22px !important;
        background: transparent !important;
        border: none !important;
        border-radius: 999px !important;
        box-shadow: none !important;
        font-size: 11px;
        line-height: 1.2;
        z-index: 1005;
    }}

    #map .mapboxgl-ctrl-attrib-button,
    #map .maplibregl-ctrl-attrib-button {{
        display: block !important;
        width: 22px !important;
        height: 22px !important;
        margin: 0 !important;
        padding: 0 !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        opacity: 1 !important;
    }}
    
    #map .mapboxgl-ctrl-attrib.mapboxgl-compact-show,
    #map .maplibregl-ctrl-attrib.maplibregl-compact-show {{
        width: 22px !important;
        min-width: 22px !important;
        height: 22px !important;
        min-height: 22px !important;
        padding: 0 !important;
        margin: 0 !important;
    }}
    
    #map .mapboxgl-ctrl-attrib.attrib-open .mapboxgl-ctrl-attrib-inner,
    #map .maplibregl-ctrl-attrib.attrib-open .maplibregl-ctrl-attrib-inner {{
        position: absolute !important;
        left: 30px !important;
        bottom: 50% !important;
        transform: translateY(50%) !important;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        white-space: nowrap !important;
    }}

    #map .mapboxgl-ctrl-attrib:not(.attrib-open) .mapboxgl-ctrl-attrib-inner,
    #map .maplibregl-ctrl-attrib:not(.attrib-open) .maplibregl-ctrl-attrib-inner {{
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }}

    #map .mapboxgl-ctrl-attrib .mapboxgl-ctrl-attrib-inner,
    #map .maplibregl-ctrl-attrib .maplibregl-ctrl-attrib-inner {{
        position: absolute;
        left: 30px;
        bottom: 50%;
        transform: translateY(50%);
        display: block !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
        transition: none !important;
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        box-shadow: none !important;
        white-space: nowrap;
    }}


    .map-controls-btn {{
        position: absolute;
        left: 28px;
        bottom: 58px;
        width: 28px;
        height: 28px;
        border: 1px solid rgba(25, 41, 48, 0.12);
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.96);
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        cursor: pointer;
        z-index: 1006;
    }}

    .map-controls-btn:hover {{
        border-color: {ACCENT};
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.10);
    }}

    .map-controls-btn svg {{
        width: 18px;
        height: 18px;
        display: block;
    }}

    .map-controls-btn svg * {{
        stroke: {TITLE_COLOUR};
    }}

    .map-controls-popup {{
        position: absolute;
        left: 28px;
        bottom: 92px;
        z-index: 1007;
        width: 300px;
        max-width: calc(100% - 56px);
    }}

    .map-controls-popup.hidden {{
        display: none;
    }}

    .map-controls-popup svg {{
        display: block;
        width: 100%;
        height: auto;
    }}

    .map-controls-popup-close {{
        position: absolute;
        top: 14px;
        right: 14px;
        z-index: 1008;
        width: 22px;
        height: 22px;
        border: none;
        background: transparent;
        color: transparent;
        cursor: pointer;
        padding: 0;
    }}

    @media (max-width: 1200px) {{
    }}

@media (max-width: 900px) {{

    html, body {{
        overflow: auto;
    }}

    .page {{
        height: auto;
        overflow: visible;
    }}

    .banner {{
        flex: none;
        height: auto;
        padding: 18px 20px 14px 20px;
    }}

    .banner h1 {{
        font-size: 34px;
        line-height: 36px;
    }}

    .banner h1 .english-highlight-banner {{
        font-size: 23.8px;
        line-height: 23.8px;
    }}

    .banner .subheading {{
        font-size: 22.68px;
        line-height: 25.92px;
    }}

    .banner .subheading .english-highlight-banner {{
        font-size: 15.876px;
        line-height: 18.144px;
    }}

    .banner .gaelic-banner {{
        padding-right: 12px;
    }}

    .banner .english-highlight-banner {{
        padding-left: 12px;
    }}

    .content {{
        flex-direction: column;
        height: auto;
        overflow: visible;
    }}

    .side-panel {{
        max-width: none;
        min-width: 0;
        min-height: 60vh;
        border-right: none;
        border-bottom: 1px solid rgba(25, 41, 48, 0.08);
    }}

    .map-panel {{
        min-height: 70vh;
    }}

    #map {{
        height: 70vh;
    }}

    .meta-line {{
        flex-direction: column;
        align-items: stretch;
    }}
    
    .meta-line-col {{
        min-width: 0;
    }}
    
    .meta-line-col-button {{
        margin-left: 0;
    }}

    .selected-place-label {{
        max-width: 280px;
        white-space: normal;
        transform: translate(16px, -100%);
    }}

    .meta-top-row {{
        flex-direction: column;
        align-items: stretch;
    }}
    
    .meta-top-item {{
        flex: 0 0 auto;
    }}
    
    .meta-top-item-button {{
        margin-left: 0;
    }}

    :root {{
        --floating-panel-width: min(74vw, 300px);
        --floating-panel-min-width: 0px;
        --floating-panel-height: 42%;
    }}

    .floating-overlays {{
        right: 12px;
        top: 48px;
        bottom: 52px;
        height: auto;
        width: min(74vw, 300px);
    }}

    .floating-inset {{
        display: none !important;
    }}

    .overlay-toggle-btn {{
        right: 12px;
        bottom: 12px;
    }}

    .inset-toggle-btn {{
        right: 60px;
        top: 12px;
    }}

}}
</style>
</head>
<body>
<div class="page">
    <header class="banner">
        <h1>
            <span class="gaelic-banner">Cainnt is Ceathramhan</span>
            <span class="english-highlight-banner">Language and Lyrics</span>
        </h1>
        
        <div class="subheading">
            <span class="gaelic-banner">Àiteachan, Daoine, Dualchasan</span>
            <span class="english-highlight-banner">Places, People, Traditions</span>
        </div>
    </header>

    <div class="content">
        <aside class="side-panel">
            <div class="side-panel-mode-toggle">
                <button id="mode-location-btn" class="mode-btn active" type="button">
                    <span class="gaelic-dark">Àitichean</span><span class="separator-accent"> | </span><span class="english-accent">Places</span>
                </button>
                <button id="mode-all-people-btn" class="mode-btn" type="button">
                    <span class="gaelic-dark">Daoine</span><span class="separator-accent"> | </span><span class="english-accent">People</span>
                </button>
            </div>
            <div id="location-panel-view" class="panel-view active">
                <div class="places-index-wrap">
                    <div class="places-index-title">Cape Breton places</div>
                    <div class="info-header">
                        <p class="intro location-intro">Click a <strong>place</strong> on the map or list to show its people and traditions.</p>
                    </div>
                    <div class="places-index-controls">
                        <span class="place-sort-label">⇅</span>
                        <button id="sort-gaelic-btn" class="place-sort-btn sort-gd active" type="button">GD</button>
                        <span class="place-sort-separator">|</span>
                        <button id="sort-english-btn" class="place-sort-btn sort-en" type="button">EN</button>
                    </div>
                    <div id="places-index-list" class="places-index-list"></div>
                </div>
            </div>

            <div id="all-people-panel-view" class="panel-view">
                <div class="info-header">
                    <p class="intro people-intro">Click on a <strong>name</strong> to view the person details and their map location.</p>
                </div>
                <div class="people-index-controls">
                    <span class="place-sort-label">⇅</span>
                    <button id="people-sort-gaelic-btn" class="place-sort-btn sort-gd active" type="button">GD</button>
                    <span class="place-sort-separator">|</span>
                    <button id="people-sort-english-btn" class="place-sort-btn sort-en" type="button">EN</button>
                </div>
                <div class="people-list-controls">
                    <button id="people-toggle-all-btn" class="tiny-btn" type="button">Collapse to letters</button>
                    <button id="people-expand-visible-btn" class="tiny-btn" type="button">Expand visible records</button>
                </div>
                <div id="all-people-list" class="people-list"></div>
            </div>
        </aside>

        <div class="map-panel">
            <div class="top-map-buttons">
                <button id="reset-map-btn" class="map-reset-btn" type="button">Reset map</button>
                <button id="show-all-cb-btn" class="map-reset-btn" type="button">Show all traditions</button>
            </div>

            <div id="floating-overlays" class="floating-panel floating-overlays combined-traditions-panel">
                <div class="floating-panel-header">
                    <div class="section-title">Associated traditions</div>
                </div>
                <div class="floating-panel-body combined-traditions-body">
                    <div class="combined-inset-block">
                        <div id="inset-selected-place-label" class="inset-selected-place-label"></div>
                        <div id="inset-map"></div>
                    </div>
                    <div class="combined-controls-block">
                        <div class="section-title">Fine control</div>
                        <p class="intro">Select or deselect traditions to highlight linked Cape Breton communities.</p>
                            <div class="filters-controls">
                                <button id="clear-all-traditions" class="tiny-btn" type="button">Clear list</button>
                                <button id="show-all-cb-pane-btn" class="tiny-btn" type="button">Show all traditions</button>
                            </div>
                        <div id="overlay-list" class="overlay-list">
                            <div class="overlay-empty">Select a Cape Breton place to load its associated traditions.</div>
                        </div>
                    </div>
                </div>
            </div>


            <button id="map-controls-btn" class="map-controls-btn" type="button" aria-label="Show map controls">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <rect x="5" y="2.5" width="8" height="13" rx="4" stroke-width="1.8"/>
                    <line x1="9" y1="2.5" x2="9" y2="6.5" stroke-width="1.8" stroke-linecap="round"/>
                    <line x1="15.5" y1="12" x2="21.5" y2="12" stroke-width="1.8" stroke-linecap="round"/>
                    <polyline points="17.8,9.8 15.5,12 17.8,14.2" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                    <polyline points="19.2,9.8 21.5,12 19.2,14.2" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                    <line x1="18.5" y1="16" x2="18.5" y2="22" stroke-width="1.8" stroke-linecap="round"/>
                    <polyline points="16.3,18.3 18.5,16 20.7,18.3" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                    <polyline points="16.3,19.7 18.5,22 20.7,19.7" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>

            <div id="map-controls-popup" class="map-controls-popup hidden" aria-hidden="true">
                <button id="map-controls-popup-close" class="map-controls-popup-close" type="button" aria-label="Close map controls"></button>
                {map_controls_svg}
            </div>

            <div id="selected-place-label" class="selected-place-label"></div>
            <div id="map"></div>
        </div>
    </div>
</div>

<script>
    const mainFigureSpec = {json.dumps(main_fig_dict, ensure_ascii=False)};
    const insetFigureSpec = {json.dumps(inset_fig_dict, ensure_ascii=False)};
    const placesLookup = {json.dumps(places_lookup, ensure_ascii=False)};
    const peopleByPlace = {json.dumps(people_lookup, ensure_ascii=False)};
    const allPeopleIndex = {json.dumps(all_people_index, ensure_ascii=False)};
    const overlayControlsAll = {json.dumps(overlay_controls_all, ensure_ascii=False)};
    const INITIAL_CENTER = {json.dumps(MAP_CENTER)};
    const INITIAL_ZOOM = {MAP_ZOOM};
    const allPlaceKeys = {json.dumps(place_keys_sorted, ensure_ascii=False)};

    function escapeHtml(value) {{
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }}

    function formatRecordingCount(value) {{
        const text = String(value ?? '').trim();
        if (!text) return '—';
        const num = Number(text);
        if (Number.isFinite(num)) {{
            return Number.isInteger(num) ? String(num) : String(num);
        }}
        return escapeHtml(text);
    }}

    function formatBilingualHtml(gaelic, english, englishClass = 'english-accent') {{
        const gd = String(gaelic || '').trim();
        const en = String(english || '').trim();

        if (gd && en) {{
            return `<span class="gaelic-dark">${{escapeHtml(gd)}}</span><span class="separator-accent"> | </span><span class="${{englishClass}}">${{escapeHtml(en)}}</span>`;
        }}
        if (en) {{
            return `<span class="${{englishClass}}">${{escapeHtml(en)}}</span>`;
        }}
        return `<span class="gaelic-dark">${{escapeHtml(gd)}}</span>`;
    }}

    function keepOnlySnapshotButton() {{
        const buttons = mapDiv.querySelectorAll('.modebar-btn');
        buttons.forEach((btn) => {{
            const title = btn.getAttribute('data-title') || '';
            if (!/download plot as a png/i.test(title)) {{
                btn.style.display = 'none';
            }}
        }});

        const groups = mapDiv.querySelectorAll('.modebar-group');
        groups.forEach((group) => {{
            const visible = [...group.querySelectorAll('.modebar-btn')]
                .some((btn) => btn.style.display !== 'none');
            if (!visible) {{
                group.style.display = 'none';
            }}
        }});
    }}

    function buildSelectedPlaceLabelHtml(place) {{
        const gaelic = place.place_name_gaelic || '';
        const english = place.place_name_english || '';

        if (gaelic && english) {{
            return `<span class="gaelic">${{escapeHtml(gaelic)}}</span><span class="separator"> | </span><span class="english">${{escapeHtml(english)}}</span>`;
        }}
        if (english) {{
            return `<span class="english">${{escapeHtml(english)}}</span>`;
        }}
        return `<span class="gaelic">${{escapeHtml(gaelic || place.place_name || '')}}</span>`;
    }}


    function renderPlaceInlineDetail(placeKey) {{
        const place = placesLookup[String(placeKey)];
        const people = (peopleByPlace[String(placeKey)] || []).slice().sort((a, b) =>
            a.sort_name.localeCompare(b.sort_name) || a.name.localeCompare(b.name)
        );

        if (!place) {{
            return '<div class="place-list-detail"><div class="empty">No data found for that place.</div></div>';
        }}

        let html = '<div class="place-list-detail">';

        if (!people.length) {{
            html += '<div class="informants-pane"><div class="empty">No people are linked to this place key.</div></div>';
        }} else {{
            let peopleHtml = '';
            for (const person of people) {{
                peopleHtml += renderPersonCard(person, {{
                    placeKey: String(placeKey),
                    latitude: place.latitude,
                    longitude: place.longitude,
                    placeOriginHtml: formatBilingualHtml(
                        place.place_name_gaelic || '',
                        place.place_name_english || ''
                    )
                }});
            }}
            html += `<div class="informants-pane">${{peopleHtml}}</div>`;
        }}

        html += '</div>';
        return html;
    }}

    let currentPlaceSort = 'gaelic';

    function getPlaceSortLabel(placeKey, mode = currentPlaceSort) {{
        const place = placesLookup[String(placeKey)] || {{}};
        if (mode === 'english') {{
            return (place.place_name_english || place.place_name_gaelic || place.place_name || '').trim();
        }}
        return (place.place_name_gaelic || place.place_name_english || place.place_name || '').trim();
    }}

    function getSortedPlaceKeys(mode = currentPlaceSort) {{
        return allPlaceKeys.slice().sort((a, b) => {{
            const aLabel = getPlaceSortLabel(a, mode).toLocaleLowerCase();
            const bLabel = getPlaceSortLabel(b, mode).toLocaleLowerCase();
            return aLabel.localeCompare(bLabel) || String(a).localeCompare(String(b));
        }});
    }}

    function updatePlaceSortButtons() {{
        if (sortGaelicBtn) sortGaelicBtn.classList.toggle('active', currentPlaceSort === 'gaelic');
        if (sortEnglishBtn) sortEnglishBtn.classList.toggle('active', currentPlaceSort === 'english');
    }}

    function renderPlacesIndex(activePlaceKey = null) {{
        if (!placesIndexList) return;

        updatePlaceSortButtons();

        const html = getSortedPlaceKeys().map((placeKey) => {{
            const place = placesLookup[String(placeKey)] || {{}};
            const isActive = String(activePlaceKey || '') === String(placeKey);
            const labelHtml = formatBilingualHtml(place.place_name_gaelic || '', place.place_name_english || '', 'english-highlight-place');
            const peopleCount = Number(place.people_count || 0);
            return `
                <div class="place-list-item${{isActive ? ' active' : ''}}" data-place-key="${{escapeHtml(String(placeKey))}}">
                    <button class="place-list-btn${{isActive ? ' active' : ''}}" type="button" data-place-key="${{escapeHtml(String(placeKey))}}">
                        <span class="place-list-name">${{labelHtml}}</span>
                        <span class="place-list-meta">Informants: ${{peopleCount}}</span>
                    </button>
                    ${{isActive ? renderPlaceInlineDetail(placeKey) : ''}}
                </div>`;
        }}).join('');

        placesIndexList.innerHTML = html;
        placesIndexList.querySelectorAll('.place-list-btn').forEach((btn) => {{
            btn.addEventListener('click', function() {{
                const placeKey = this.dataset.placeKey;
                const isAlreadyActive = String(currentLocationPlaceKey || '') === String(placeKey);
                if (isAlreadyActive) {{
                    clearActivePlaceSelection();
                    return;
                }}
                activatePlace(placeKey, {{ source: 'list' }});
            }});
        }});
    }}

    function setActivePlaceInList(placeKey = null) {{
        renderPlacesIndex(placeKey);
        if (!placeKey || !placesIndexList) return;
        const activeItem = placesIndexList.querySelector('.place-list-item.active');
        if (activeItem && typeof activeItem.scrollIntoView === 'function') {{
            activeItem.scrollIntoView({{ block: 'nearest' }});
        }}
    }}

    function setPlaceSort(mode) {{
        currentPlaceSort = mode === 'english' ? 'english' : 'gaelic';
        setActivePlaceInList(currentLocationPlaceKey);
    }}

    function renderPersonCard(person, options = {{}}) {{
    const placeKey = options.placeKey || person.place_key || '';
    const latitude = options.latitude || person.latitude || '';
    const longitude = options.longitude || person.longitude || '';
    const placeOriginHtml = options.placeOriginHtml || '—';

    const gaelicName = person.gaelic_name || '';
    const englishName = person.english_name || '';

    let summaryName = '';
    if (gaelicName && englishName) {{
        summaryName = `${{escapeHtml(gaelicName)}}<span class="separator-accent"> / </span><span class="english-highlight-person">${{escapeHtml(englishName)}}</span>`;
    }} else if (englishName) {{
        summaryName = `<span class="english-highlight-person">${{escapeHtml(englishName)}}</span>`;
    }} else {{
        summaryName = escapeHtml(gaelicName || person.display_name || person.id || 'Unnamed person');
    }}

    return `
        <details class="person-card"
            data-place-key="${{escapeHtml(String(placeKey))}}"
            data-lat="${{escapeHtml(String(latitude))}}"
            data-lon="${{escapeHtml(String(longitude))}}">
            <summary><span class="person-summary-name">${{summaryName}}</span></summary>
            <div class="metadata">
                <div class="meta-top-row">
                    <div class="meta-top-item">
                        <div class="meta-label">ID</div>
                        <div class="meta-inline-value">${{escapeHtml(person.id || '—')}}</div>
                    </div>
                    <div class="meta-top-item">
                        <div class="meta-label">Dates</div>
                        <div class="meta-inline-value">${{escapeHtml(person.yob_yod || '—')}}</div>
                    </div>
                    <div class="meta-top-item meta-top-item-button">
                        ${{
                            person.person_page_url
                                ? `<a class="person-page-link-btn" href="${{escapeHtml(person.person_page_url)}}" target="_blank" rel="noopener noreferrer">View person page</a>`
                                : ''
                        }}
                    </div>
                </div>

                <div class="meta-block">
                    <div class="meta-label">Sloinneadh</div>
                    <div class="meta-value">${{escapeHtml(person.sloinneadh || '—')}}</div>
                </div>

                <div class="meta-block">
                    <div class="meta-label">Place of origin</div>
                    <div class="meta-value">${{placeOriginHtml}}</div>
                </div>

                <div class="meta-block recordings-meta-block">
                    <div class="recordings-meta-row">
                        <div class="recordings-meta-left">
                            <div class="meta-label">Number of recordings</div>
                            <div class="meta-value">${{formatRecordingCount(person.number_of_recordings)}}</div>
                        </div>
                        ${{
                            person.recordings_url
                                ? `<a class="recordings-link-btn" href="${{escapeHtml(person.recordings_url)}}" target="_blank" rel="noopener noreferrer">View all recordings</a>`
                                : ''
                        }}
                    </div>
                </div>
            </div>
        </details>`;
}}

    function resetInfoPanel() {{
        currentLocationPlaceKey = null;
        renderPlacesIndex(null);
    }}

    function clearActivePlaceSelection() {{
        currentLocationPlaceKey = null;
        renderPlacesIndex(null);
        clearSelectedPerson({{ restoreActivePlace: false }});
        clearAllTraditionsAndControls();
    }}

    function clearSelectionRing() {{
        Plotly.restyle(mapDiv, {{lat: [[], []], lon: [[], []]}}, [1, 2]);
    }}

    function clearInsetSelectionRing() {{
        Plotly.restyle(insetMapDiv, {{lat: [[], []], lon: [[], []]}}, [0, 1]);
    }}

    function hideSelectedPlaceLabel() {{
        selectedPlaceState = null;
        selectedPlaceLabel.style.display = 'none';
        selectedPlaceLabel.innerHTML = '';
    }}

    function hideInsetSelectedPlaceLabel() {{
        insetSelectedPlaceState = null;
        insetSelectedPlaceLabel.style.display = 'none';
        insetSelectedPlaceLabel.innerHTML = '';
    }}

    function positionSelectedPlaceLabel() {{
        if (!selectedPlaceState || !subplotMap || typeof subplotMap.project !== 'function') {{
            return;
        }}

        const projected = subplotMap.project([selectedPlaceState.lon, selectedPlaceState.lat]);
        if (!projected) {{
            return;
        }}

        selectedPlaceLabel.style.left = `${{projected.x}}px`;
        selectedPlaceLabel.style.top = `${{projected.y}}px`;
        selectedPlaceLabel.style.display = 'block';
    }}

    function positionInsetSelectedPlaceLabel() {{
        if (!insetSelectedPlaceState || !insetSubplotMap || typeof insetSubplotMap.project !== 'function') {{
            return;
        }}

        const projected = insetSubplotMap.project([insetSelectedPlaceState.lon, insetSelectedPlaceState.lat]);
        if (!projected) {{
            return;
        }}

        insetSelectedPlaceLabel.style.left = `${{projected.x}}px`;
        insetSelectedPlaceLabel.style.top = `${{projected.y}}px`;
        insetSelectedPlaceLabel.style.display = 'block';
    }}

    function showSelectedPlaceLabel(place, lat, lon) {{
        selectedPlaceState = {{
            lat: lat,
            lon: lon,
            html: buildSelectedPlaceLabelHtml(place),
        }};

        selectedPlaceLabel.innerHTML = selectedPlaceState.html;
        positionSelectedPlaceLabel();
    }}

    function showInsetSelectedPlaceLabel(customPlaceName, lat, lon) {{
        const [gaelic, english] = String(customPlaceName || '').includes('|')
            ? customPlaceName.split('|', 2).map((s) => s.trim())
            : [String(customPlaceName || '').trim(), ''];

        let html = '';
        if (gaelic && english) {{
            html = `<span class="gaelic">${{escapeHtml(gaelic)}}</span><span class="separator"> | </span><span class="english">${{escapeHtml(english)}}</span>`;
        }} else if (english) {{
            html = `<span class="english">${{escapeHtml(english)}}</span>`;
        }} else {{
            html = `<span class="gaelic">${{escapeHtml(gaelic)}}</span>`;
        }}

        insetSelectedPlaceState = {{
            lat: lat,
            lon: lon,
            html: html,
        }};

        insetSelectedPlaceLabel.innerHTML = html;
        positionInsetSelectedPlaceLabel();
    }}

    function setAllTraditionsVisibleByKeys(keys, checkedValue) {{
        const keySet = new Set(keys.map(String));
        const mainTraceIndexes = [];
        const mainVisible = [];
        const insetTraceIndexes = [];
        const insetVisible = [];

        for (const item of overlayControlsAll) {{
            const show = keySet.has(String(item.tradition_key)) && checkedValue;
            mainTraceIndexes.push(item.main_trace_index);
            mainVisible.push(show);
            insetTraceIndexes.push(item.inset_trace_index);
            insetVisible.push(show);
        }}

        if (mainTraceIndexes.length) {{
            Plotly.restyle(mapDiv, {{visible: mainVisible}}, mainTraceIndexes);
        }}
        if (insetTraceIndexes.length) {{
            Plotly.restyle(insetMapDiv, {{visible: insetVisible}}, insetTraceIndexes);
        }}
    }}

    function updateOverlayListActionButton() {{
        if (!clearAllTraditionsBtn) return;
    
        const hasList = currentOverlayTraditionKeys.length > 0;
        if (!hasList) {{
            clearAllTraditionsBtn.textContent = 'Clear list';
            clearAllTraditionsBtn.disabled = true;
            overlayListCleared = false;
            return;
        }}
    
        clearAllTraditionsBtn.disabled = false;
        clearAllTraditionsBtn.textContent = overlayListCleared ? 'Restore list' : 'Clear list';
    }}
    
    function clearAllTraditionsAndControls() {{
        currentOverlayTraditionKeys = [];
        overlayListCleared = false;
        setAllTraditionsVisibleByKeys([], false);
        renderOverlayControls([]);
        updateOverlayListActionButton();
        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();
        Plotly.redraw(mapDiv);
        Plotly.redraw(insetMapDiv);
    }}

    function showAllTraditionsInCapeBreton() {{
        currentLocationPlaceKey = null;
        resetInfoPanel();
        clearSelectedPerson();
        clearSelectionRing();
        hideSelectedPlaceLabel();
        const allKeys = overlayControlsAll.map((item) => String(item.tradition_key));
        currentOverlayTraditionKeys = allKeys.slice();
        overlayListCleared = false;
        renderPlacesIndex(null);
        renderOverlayControls(currentOverlayTraditionKeys, true);
        setAllTraditionsVisibleByKeys(currentOverlayTraditionKeys, true);
        updateOverlayListActionButton();
        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();
        Plotly.redraw(mapDiv);
        Plotly.redraw(insetMapDiv);
    }}

    function resetMainMapAndPanels() {{
        clearActivePlaceSelection();

        Plotly.relayout(mapDiv, {{
            'map.center.lat': INITIAL_CENTER.lat,
            'map.center.lon': INITIAL_CENTER.lon,
            'map.zoom': INITIAL_ZOOM
        }});
    }}
    
    let currentOverlayTraditionKeys = [];
    let overlayListCleared = false;

    function showLocationTraditionsSection(placeKey) {{
        const place = placesLookup[String(placeKey)];
        if (!place) {{
            currentOverlayTraditionKeys = [];
            overlayListCleared = false;
            renderOverlayControls([]);
            setAllTraditionsVisibleByKeys([], false);
            updateOverlayListActionButton();
            clearInsetSelectionRing();
            hideInsetSelectedPlaceLabel();
            Plotly.redraw(mapDiv);
            Plotly.redraw(insetMapDiv);
            return;
        }}
    
        const associatedKeys = (place.traditions || []).map((item) => String(item.key));
        currentOverlayTraditionKeys = associatedKeys.slice();
        overlayListCleared = false;
    
        renderOverlayControls(currentOverlayTraditionKeys, true);
        setAllTraditionsVisibleByKeys(currentOverlayTraditionKeys, true);
        updateOverlayListActionButton();
    
        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();
    
        Plotly.redraw(mapDiv);
        Plotly.redraw(insetMapDiv);
    }}

    function renderPlace(placeKey) {{
        const place = placesLookup[String(placeKey)];

        if (!place) {{
            renderPlacesIndex(null);
            renderOverlayControls([]);
            return;
        }}

        currentLocationPlaceKey = String(placeKey);
        setActivePlaceInList(currentLocationPlaceKey);
        showLocationTraditionsSection(currentLocationPlaceKey);
        wireLocationPersonSelectionBehaviour();
    }}

    function activatePlace(placeKey, options = {{}}) {{
        const place = placesLookup[String(placeKey)];
        if (!place) return;

        clearSelectedPerson({{ restoreActivePlace: false }});
        currentLocationPlaceKey = String(placeKey);
        setSidePanelMode('location');
        renderPlace(placeKey);
        Plotly.restyle(
            mapDiv,
            {{ lat: [[place.latitude], [place.latitude]], lon: [[place.longitude], [place.longitude]] }},
            [1, 2]
        );
        showSelectedPlaceLabel(place, place.latitude, place.longitude);
    }}

    function buildOverlayRowHtml(item, checked) {{
        const labelHtml = formatBilingualHtml(item.label_gaelic || '', item.label_english || '');

        return `
            <label class="overlay-row">
                <input type="checkbox" class="tradition-toggle" data-tradition-key="${{item.tradition_key}}" data-main-trace-index="${{item.main_trace_index}}" data-inset-trace-index="${{item.inset_trace_index}}" ${{checked ? 'checked' : ''}}>
                <span class="colour-chip" style="background:${{item.colour}};"></span>
                <span class="overlay-label">${{labelHtml}}</span>
            </label>`;
    }}

    function renderOverlayControls(activeTraditionKeys, checkedState = true) {{
        const keySet = new Set((activeTraditionKeys || []).map(String));
        const items = overlayControlsAll.filter((item) => keySet.has(String(item.tradition_key)));
    
        if (!items.length) {{
            overlayList.innerHTML = '<div class="overlay-empty">Select a Cape Breton place to load associated traditions.</div>';
            updateOverlayListActionButton();
            return;
        }}
    
        overlayList.innerHTML = items.map((item) => buildOverlayRowHtml(item, checkedState)).join('');
        updateOverlayListActionButton();
    
        document.querySelectorAll('.tradition-toggle').forEach((checkbox) => {{
            checkbox.addEventListener('change', function() {{
                const mainTraceIndex = Number(this.dataset.mainTraceIndex);
                const insetTraceIndex = Number(this.dataset.insetTraceIndex);
                const visibleValue = this.checked;
    
                Plotly.restyle(mapDiv, {{visible: visibleValue}}, [mainTraceIndex]);
                Plotly.restyle(insetMapDiv, {{visible: visibleValue}}, [insetTraceIndex]);
    
                clearInsetSelectionRing();
                hideInsetSelectedPlaceLabel();
                Plotly.redraw(mapDiv);
                Plotly.redraw(insetMapDiv);
            }});
        }});
    }}

    function setAllVisibleInCurrentOverlayPane(isVisible) {{
        const checkboxes = [...document.querySelectorAll('.tradition-toggle')];
        if (!checkboxes.length) return;

        const mainTraceIndexes = [];
        const insetTraceIndexes = [];
        const visibleValues = [];

        checkboxes.forEach((checkbox) => {{
            checkbox.checked = isVisible;
            mainTraceIndexes.push(Number(checkbox.dataset.mainTraceIndex));
            insetTraceIndexes.push(Number(checkbox.dataset.insetTraceIndex));
            visibleValues.push(isVisible);
        }});

        Plotly.restyle(mapDiv, {{visible: visibleValues}}, mainTraceIndexes);
        Plotly.restyle(insetMapDiv, {{visible: visibleValues}}, insetTraceIndexes);

        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();
        Plotly.redraw(mapDiv);
        Plotly.redraw(insetMapDiv);
    }}

    function setOverlayPanelVisibility(isVisible) {{
        floatingOverlays.classList.remove('hidden');
    }}

    function setInsetPanelVisibility(isVisible) {{
        if (floatingInset) {{
            floatingInset.classList.remove('hidden');
        }}
        setTimeout(() => {{
            Plotly.Plots.resize(insetMapDiv);
        }}, 0);
    }}

    function setSidePanelMode(mode) {{
        const showLocation = mode === 'location';
        locationPanelView.classList.toggle('active', showLocation);
        allPeoplePanelView.classList.toggle('active', !showLocation);
        modeLocationBtn.classList.toggle('active', showLocation);
        modeAllPeopleBtn.classList.toggle('active', !showLocation);

        if (showLocation) {{
            clearSelectedPerson();
        }}
    }}

    let currentPeopleSort = 'gaelic';

    function getPeopleSurnameForSort(person, mode = currentPeopleSort) {{
        if (mode === 'english') {{
            return (person.english_last || person.gaelic_last || person.sloinneadh || person.english_name || person.display_name || '').trim();
        }}
        return (person.gaelic_last || person.sloinneadh || person.english_last || person.gaelic_name || person.display_name || '').trim();
    }}

    function getPeopleGivenForSort(person, mode = currentPeopleSort) {{
        if (mode === 'english') {{
            return (person.english_first || person.english_name || person.gaelic_first || person.display_name || '').trim();
        }}
        return (person.gaelic_first || person.english_first || person.gaelic_name || person.english_name || person.display_name || '').trim();
    }}

    function getPeopleLetter(person, mode = currentPeopleSort) {{
        const source = getPeopleSurnameForSort(person, mode) || person.display_name || '#';
        const initial = (source.trim().charAt(0) || '#').toUpperCase();
        return /[A-Za-zÀ-ÖØ-öø-ÿ]/.test(initial) ? initial : '#';
    }}

    function getSortedPeopleIndex(mode = currentPeopleSort) {{
        return allPeopleIndex.slice().sort((a, b) => {{
            const aSurname = getPeopleSurnameForSort(a, mode).toLocaleLowerCase();
            const bSurname = getPeopleSurnameForSort(b, mode).toLocaleLowerCase();
            const surnameCmp = aSurname.localeCompare(bSurname);
            if (surnameCmp !== 0) return surnameCmp;

            const aGiven = getPeopleGivenForSort(a, mode).toLocaleLowerCase();
            const bGiven = getPeopleGivenForSort(b, mode).toLocaleLowerCase();
            const givenCmp = aGiven.localeCompare(bGiven);
            if (givenCmp !== 0) return givenCmp;

            return String(a.id || a.display_name || '').localeCompare(String(b.id || b.display_name || ''));
        }});
    }}

    function updatePeopleSortButtons() {{
        if (peopleSortGaelicBtn) peopleSortGaelicBtn.classList.toggle('active', currentPeopleSort === 'gaelic');
        if (peopleSortEnglishBtn) peopleSortEnglishBtn.classList.toggle('active', currentPeopleSort === 'english');
    }}

    function buildAllPeopleListHtml() {{
        if (!allPeopleIndex.length) {{
            return '<div class="people-empty">No people found.</div>';
        }}

        updatePeopleSortButtons();

        const grouped = {{}};
        for (const person of getSortedPeopleIndex()) {{
            const letter = getPeopleLetter(person, currentPeopleSort);
            if (!grouped[letter]) grouped[letter] = [];
            grouped[letter].push(person);
        }}

        const letters = Object.keys(grouped).sort((a, b) => a.localeCompare(b));
        let html = '';

        for (const letter of letters) {{
            html += `<details class="people-letter-group" open>`;
            html += `<summary>${{escapeHtml(letter)}}</summary>`;
            html += `<div class="people-letter-group-body">`;

            for (const person of grouped[letter]) {{
                const placeLabel = formatBilingualHtml(
                    person.place_name_gaelic || '',
                    person.place_name_english || ''
                );

                html += renderPersonCard(person, {{
                    placeKey: String(person.place_key || ''),
                    latitude: person.latitude || '',
                    longitude: person.longitude || '',
                    placeOriginHtml: placeLabel
                }});
            }}

            html += `</div></details>`;
        }}

        return html;
    }}

    function setPeopleSort(mode) {{
        currentPeopleSort = mode === 'english' ? 'english' : 'gaelic';
        renderAllPeopleList();
    }}

    function highlightPlaceFromPersonCard(placeKey, lat, lon) {{
            const place = placesLookup[String(placeKey)];
            if (!place) return;
    
            Plotly.restyle(
                mapDiv,
                {{
                    lat: [[lat], [lat]],
                    lon: [[lon], [lon]]
                }},
                [1, 2]
            );
    
            showSelectedPlaceLabel(place, lat, lon);
        }}

    let selectedPersonCard = null;

    function clearSelectedPerson(options = {{}}) {{
        const restoreActivePlace = options.restoreActivePlace !== false;

        document.querySelectorAll('details.person-card.selected').forEach((card) => {{
            card.classList.remove('selected');
        }});
    
        selectedPersonCard = null;

        if (restoreActivePlace && currentLocationPlaceKey) {{
            const activePlace = placesLookup[String(currentLocationPlaceKey)];
            if (activePlace) {{
                Plotly.restyle(
                    mapDiv,
                    {{
                        lat: [[activePlace.latitude], [activePlace.latitude]],
                        lon: [[activePlace.longitude], [activePlace.longitude]]
                    }},
                    [1, 2]
                );
                showSelectedPlaceLabel(activePlace, activePlace.latitude, activePlace.longitude);
                return;
            }}
        }}

        clearSelectionRing();
        hideSelectedPlaceLabel();
    }}
    
    function selectPersonCard(card) {{
        if (!card) return;
    
        document.querySelectorAll('details.person-card.selected').forEach((el) => {{
            if (el !== card) el.classList.remove('selected');
        }});
    
        selectedPersonCard = card;
        selectedPersonCard.classList.add('selected');
    
        const placeKey = card.dataset.placeKey;
        const lat = Number(card.dataset.lat);
        const lon = Number(card.dataset.lon);
        const place = placesLookup[String(placeKey)];
        if (!place) return;

        const previousPlaceKey = String(currentLocationPlaceKey || '');
        const nextPlaceKey = String(placeKey || '');
        const clickedInsideActivePlaceList = !!card.closest('#places-index-list .place-list-detail');

        currentLocationPlaceKey = nextPlaceKey;

        if (!(clickedInsideActivePlaceList && previousPlaceKey === nextPlaceKey)) {{
            setActivePlaceInList(currentLocationPlaceKey);
        }}

        showLocationTraditionsSection(currentLocationPlaceKey);
    
        Plotly.restyle(
            mapDiv,
            {{
                lat: [[lat], [lat]],
                lon: [[lon], [lon]]
            }},
            [1, 2]
        );
    
        showSelectedPlaceLabel(place, lat, lon);
    }}
    
    function wirePersonSelectionBehaviour() {{
        document.querySelectorAll('#all-people-list details.person-card').forEach((card) => {{
            const summary = card.querySelector(':scope > summary');
            if (!summary) return;

            summary.addEventListener('click', function() {{
                const toggleOff = card.classList.contains('selected') && card.open;
                window.setTimeout(() => {{
                    if (toggleOff) {{
                        clearSelectedPerson({{ restoreActivePlace: false }});
                        currentLocationPlaceKey = null;
                        renderPlacesIndex(null);
                        clearAllTraditionsAndControls();
                    }} else {{
                        selectPersonCard(card);
                    }}
                }}, 0);
            }});
        }});
    }}

    function renderAllPeopleList() {{
        allPeopleList.innerHTML = buildAllPeopleListHtml();
        wirePersonSelectionBehaviour();
        visibleRecordsExpanded = false;
        previousVisibleRecordStates = new Map();
        allPeopleShown = true;
        if (peopleToggleAllBtn) {{
            peopleToggleAllBtn.textContent = 'Collapse to letters';
        }}
    }}
    
    function openAllLetterGroups() {{
        document.querySelectorAll('#all-people-list details.people-letter-group').forEach((el) => {{
            el.open = true;
        }});
        visibleRecordsExpanded = false;
        previousVisibleRecordStates = new Map();
        allPeopleShown = true;
        if (peopleToggleAllBtn) {{
            peopleToggleAllBtn.textContent = 'Collapse to letters';
        }}
    }}
    
    function collapseAllLetterGroups() {{
        document.querySelectorAll('#all-people-list details.people-letter-group').forEach((el) => {{
            el.open = false;
        }});
        document.querySelectorAll('#all-people-list details.person-card').forEach((el) => {{
            el.open = false;
        }});
        visibleRecordsExpanded = false;
        previousVisibleRecordStates = new Map();
        allPeopleShown = false;
        if (peopleToggleAllBtn) {{
            peopleToggleAllBtn.textContent = 'Show all names';
        }}
    }}
    
    function toggleAllLetterGroups() {{
        if (allPeopleShown) {{
            collapseAllLetterGroups();
        }} else {{
            openAllLetterGroups();
            document.querySelectorAll('#all-people-list details.all-people-card').forEach((el) => {{
                el.open = false;
            }});
            visibleRecordsExpanded = false;
            previousVisibleRecordStates = new Map();
        }}
    }}
    
    function expandVisiblePeopleRecords() {{
        const visibleCards = [];
    
        document.querySelectorAll('#all-people-list details.people-letter-group').forEach((group, groupIndex) => {{
            if (!group.open) return;
    
            const cards = group.querySelectorAll('details.person-card');
            cards.forEach((card, cardIndex) => {{
                visibleCards.push({{
                    key: `${{groupIndex}}-${{cardIndex}}`,
                    card: card
                }});
            }});
        }});
    
        if (!visibleRecordsExpanded) {{
            previousVisibleRecordStates = new Map();
            visibleCards.forEach(({{ key, card }}) => {{
                previousVisibleRecordStates.set(key, card.open);
                card.open = true;
            }});
            visibleRecordsExpanded = true;
        }} else {{
            visibleCards.forEach(({{key, card}}) => {{
                card.open = previousVisibleRecordStates.has(key)
                    ? previousVisibleRecordStates.get(key)
                    : false;
            }});
            visibleRecordsExpanded = false;
        }}
    }}
    
    function wireLocationPersonSelectionBehaviour() {{
        document.querySelectorAll('#places-index-list .place-list-detail details.person-card').forEach((card) => {{
            const summary = card.querySelector(':scope > summary');
            if (!summary) return;

            summary.addEventListener('click', function() {{
                const toggleOff = card.classList.contains('selected') && card.open;
                window.setTimeout(() => {{
                    if (toggleOff) {{
                        clearSelectedPerson({{ restoreActivePlace: true }});
                    }} else {{
                        selectPersonCard(card);
                    }}
                }}, 0);
            }});
        }});
    }}
    
    const mapDiv = document.getElementById('map');
    const insetMapDiv = document.getElementById('inset-map');
    const resetBtn = document.getElementById('reset-map-btn');
    const showAllCbBtn = document.getElementById('show-all-cb-btn');
    const showAllCbPaneBtn = document.getElementById('show-all-cb-pane-btn');
    const selectedPlaceLabel = document.getElementById('selected-place-label');
    const insetSelectedPlaceLabel = document.getElementById('inset-selected-place-label');
    const overlayList = document.getElementById('overlay-list');
    const clearAllTraditionsBtn = document.getElementById('clear-all-traditions');
    const floatingOverlays = document.getElementById('floating-overlays');
    const floatingInset = document.getElementById('floating-inset');
    const placesIndexList = document.getElementById('places-index-list');
    const sortGaelicBtn = document.getElementById('sort-gaelic-btn');
    const sortEnglishBtn = document.getElementById('sort-english-btn');
    const peopleSortGaelicBtn = document.getElementById('people-sort-gaelic-btn');
    const peopleSortEnglishBtn = document.getElementById('people-sort-english-btn');

    if (sortGaelicBtn) {{
        sortGaelicBtn.addEventListener('click', () => setPlaceSort('gaelic'));
    }}
    if (sortEnglishBtn) {{
        sortEnglishBtn.addEventListener('click', () => setPlaceSort('english'));
    }}
    if (peopleSortGaelicBtn) {{
        peopleSortGaelicBtn.addEventListener('click', () => setPeopleSort('gaelic'));
    }}
    if (peopleSortEnglishBtn) {{
        peopleSortEnglishBtn.addEventListener('click', () => setPeopleSort('english'));
    }}
    const modeLocationBtn = document.getElementById('mode-location-btn');
    const modeAllPeopleBtn = document.getElementById('mode-all-people-btn');
    const locationPanelView = document.getElementById('location-panel-view');
    const allPeoplePanelView = document.getElementById('all-people-panel-view');
    const allPeopleList = document.getElementById('all-people-list');
    const peopleToggleAllBtn = document.getElementById('people-toggle-all-btn');
    const peopleExpandVisibleBtn = document.getElementById('people-expand-visible-btn');
    const mapControlsBtn = document.getElementById('map-controls-btn');
    const mapControlsPopup = document.getElementById('map-controls-popup');
    const mapControlsPopupClose = document.getElementById('map-controls-popup-close');

    let selectedPlaceState = null;
    let insetSelectedPlaceState = null;
    let subplotMap = null;
    let insetSubplotMap = null;
    let suppressNextMainBackgroundClick = false;
    let suppressNextInsetBackgroundClick = false;
    let visibleRecordsExpanded = false;
    let previousVisibleRecordStates = new Map();
    let allPeopleShown = true;
    let currentLocationPlaceKey = null;

    function wireMainMapAttributionToggle() {{
        const attrib =
            mapDiv.querySelector('.mapboxgl-ctrl-attrib, .maplibregl-ctrl-attrib');
    
        if (!attrib) return;
    
        const originalButton =
            attrib.querySelector('.mapboxgl-ctrl-attrib-button, .maplibregl-ctrl-attrib-button');
    
        if (!originalButton) return;
    
        if (attrib.dataset.customAttribWired === '1') return;
        attrib.dataset.customAttribWired = '1';
    
        const newButton = originalButton.cloneNode(true);
        originalButton.parentNode.replaceChild(newButton, originalButton);
    
        newButton.addEventListener('click', function(event) {{
            event.preventDefault();
            event.stopPropagation();
            attrib.classList.toggle('attrib-open');
        }});
    
        attrib.addEventListener('click', function(event) {{
            event.stopPropagation();
        }});
    
        document.addEventListener('click', function(event) {{
            if (!attrib.contains(event.target)) {{
                attrib.classList.remove('attrib-open');
            }}
        }});
    }}


    function setMapControlsPopupVisibility(show) {{
        if (!mapControlsPopup) return;
        mapControlsPopup.classList.toggle('hidden', !show);
        mapControlsPopup.setAttribute('aria-hidden', show ? 'false' : 'true');
    }}

    function wireMapControlsPopup() {{
        if (!mapControlsBtn || !mapControlsPopup) return;

        mapControlsBtn.addEventListener('click', function(event) {{
            event.preventDefault();
            event.stopPropagation();
            const willShow = mapControlsPopup.classList.contains('hidden');
            setMapControlsPopupVisibility(willShow);
        }});

        mapControlsPopup.addEventListener('click', function(event) {{
            event.stopPropagation();
        }});

        if (mapControlsPopupClose) {{
            mapControlsPopupClose.addEventListener('click', function(event) {{
                event.preventDefault();
                event.stopPropagation();
                setMapControlsPopupVisibility(false);
            }});
        }}

        document.addEventListener('click', function(event) {{
            const clickedInside = mapControlsPopup.contains(event.target) || mapControlsBtn.contains(event.target);
            if (!clickedInside) {{
                setMapControlsPopupVisibility(false);
            }}
        }});

        document.addEventListener('keydown', function(event) {{
            if (event.key === 'Escape') {{
                setMapControlsPopupVisibility(false);
            }}
        }});
    }}

    Plotly.newPlot(
        mapDiv,
        mainFigureSpec.data,
        mainFigureSpec.layout,
        {{
            responsive: true,
            displaylogo: false,
            displayModeBar: false
        }}
    ).then(function() {{
        wireMainMapAttributionToggle();
        wireMapControlsPopup();

        Plotly.newPlot(
            insetMapDiv,
            insetFigureSpec.data,
            insetFigureSpec.layout,
            {{
                responsive: true,
                displaylogo: false,
                displayModeBar: false,
                staticPlot: false
            }}
        ).then(function() {{
            renderPlacesIndex(null);
            renderOverlayControls([]);
            updateOverlayListActionButton();
            setOverlayPanelVisibility(true);
            setInsetPanelVisibility(true);
            setSidePanelMode('location');
            resetInfoPanel();

            setTimeout(() => {{
                renderAllPeopleList();
            }}, 0);

            insetSubplotMap =
                insetMapDiv?._fullLayout?.map?._subplot?.map ||
                insetMapDiv?._fullLayout?.mapbox?._subplot?.map ||
                null;

            if (insetSubplotMap && typeof insetSubplotMap.on === 'function') {{
                insetSubplotMap.on('move', function() {{
                    positionInsetSelectedPlaceLabel();
                }});

                insetSubplotMap.on('zoom', function() {{
                    positionInsetSelectedPlaceLabel();
                }});

                insetSubplotMap.on('resize', function() {{
                    positionInsetSelectedPlaceLabel();
                }});

                insetSubplotMap.on('click', function() {{
                    if (suppressNextInsetBackgroundClick) {{
                        suppressNextInsetBackgroundClick = false;
                        return;
                    }}
                    clearInsetSelectionRing();
                    hideInsetSelectedPlaceLabel();
                }});
            }}

            insetMapDiv.on('plotly_click', function(eventData) {{
                if (!eventData || !eventData.points || !eventData.points.length) return;
                const point = eventData.points[0];
                if (!point.customdata || !point.customdata.length) return;
                if (point.curveNumber < 2) return;

                suppressNextInsetBackgroundClick = true;

                const placeName = point.customdata[1];
                Plotly.restyle(
                    insetMapDiv,
                    {{
                        lat: [[point.lat], [point.lat]],
                        lon: [[point.lon], [point.lon]]
                    }},
                    [0, 1]
                );
                showInsetSelectedPlaceLabel(placeName, point.lat, point.lon);
            }});

            insetMapDiv.on('plotly_relayout', function() {{
                positionInsetSelectedPlaceLabel();
            }});
        }});

        subplotMap =
            mapDiv?._fullLayout?.map?._subplot?.map ||
            mapDiv?._fullLayout?.mapbox?._subplot?.map ||
            null;

        mapDiv.on('plotly_click', function(eventData) {{
            if (!eventData || !eventData.points || !eventData.points.length) {{
                return;
            }}

            const point = eventData.points[0];
            if (!point.customdata || !point.customdata.length) {{
                return;
            }}

            suppressNextMainBackgroundClick = true;

            const placeKey = point.customdata[0];
            activatePlace(placeKey, {{ source: 'map' }});
        }});

        mapDiv.on('plotly_relayout', function() {{
            positionSelectedPlaceLabel();
        }});

        if (subplotMap && typeof subplotMap.on === 'function') {{
            subplotMap.on('move', function() {{
                positionSelectedPlaceLabel();
            }});

            subplotMap.on('zoom', function() {{
                positionSelectedPlaceLabel();
            }});

            subplotMap.on('resize', function() {{
                positionSelectedPlaceLabel();
            }});

            subplotMap.on('click', function() {{
                if (suppressNextMainBackgroundClick) {{
                    suppressNextMainBackgroundClick = false;
                    return;
                }}
                clearSelectedPerson();
                resetMainMapAndPanels();
            }});
        }}
    }});

    resetBtn.addEventListener('click', function() {{
        resetMainMapAndPanels();
    }});

    showAllCbBtn.addEventListener('click', function() {{
        showAllTraditionsInCapeBreton();
    }});

    showAllCbPaneBtn.addEventListener('click', function() {{
        showAllTraditionsInCapeBreton();
    }});

    clearAllTraditionsBtn.addEventListener('click', function() {{
        if (!currentOverlayTraditionKeys.length) return;
    
        if (!overlayListCleared) {{
            setAllVisibleInCurrentOverlayPane(false);
            overlayListCleared = true;
        }} else {{
            setAllVisibleInCurrentOverlayPane(true);
            overlayListCleared = false;
        }}
    
        updateOverlayListActionButton();
    }});

    modeLocationBtn.addEventListener('click', function() {{
        setSidePanelMode('location');
    }});

    modeAllPeopleBtn.addEventListener('click', function() {{
        setSidePanelMode('all');
        if (peopleToggleAllBtn) {{
            peopleToggleAllBtn.textContent = allPeopleShown ? 'Collapse list to letters' : 'Show all names';
        }}
    }});

        peopleToggleAllBtn.addEventListener('click', function() {{
        toggleAllLetterGroups();
    }});
    
    peopleExpandVisibleBtn.addEventListener('click', function() {{
        expandVisiblePeopleRecords();
    }});

    document.addEventListener('click', function(event) {{
        const clickedPersonCard = event.target.closest('details.person-card');
        if (clickedPersonCard) return;
    
        const clickedMapMarker = event.target.closest('#map, #selected-place-label');
        if (clickedMapMarker) return;

        const clickedPlaceListControl = event.target.closest('#places-index-list, .places-index-controls');
        if (clickedPlaceListControl) return;
    
        clearSelectedPerson();
    }});


</script>
</body>
</html>
"""

    output_path.write_text(html, encoding="utf-8")


def main() -> None:
    base_dir = Path(__file__).resolve().parent

    places_path = base_dir / PLACES_CSV
    people_path = base_dir / PEOPLE_CSV
    communities_path = base_dir / COMMUNITIES_CSV
    traditions_path = base_dir / TRADITIONS_CSV
    output_path = base_dir / OUTPUT_HTML

    all_places_df = clean_places(pd.read_csv(places_path, encoding="utf-8-sig"))
    people_df = clean_people(pd.read_csv(people_path, encoding="utf-8-sig"))
    communities_df = clean_communities(pd.read_csv(communities_path, encoding="utf-8-sig"))
    traditions_df = clean_traditions(pd.read_csv(traditions_path, encoding="utf-8-sig"))

    cape_breton_keys = set(people_df["Place number"].astype(int).tolist())
    cape_breton_keys.update(communities_df["Community"].astype(int).tolist())
    for keys in traditions_df["Community_keys"]:
        cape_breton_keys.update(keys)

    cape_breton_places_df = all_places_df[all_places_df["place_key"].isin(cape_breton_keys)].copy()

    people_counts = (
        people_df.groupby("Place number").size().rename("people_count").reset_index()
    )

    cape_breton_places_df = cape_breton_places_df.merge(
        people_counts,
        left_on="place_key",
        right_on="Place number",
        how="left",
    )
    cape_breton_places_df["people_count"] = cape_breton_places_df["people_count"].fillna(0).astype(int)
    cape_breton_places_df = cape_breton_places_df.drop(columns=["Place number"], errors="ignore")

    people_counts_lookup = dict(
        zip(
            cape_breton_places_df["place_key"].astype(int),
            cape_breton_places_df["people_count"].astype(int),
            strict=False,
        )
    )

    people_lookup = build_people_lookup(people_df)
    all_people_index = build_all_people_index(people_df, cape_breton_places_df)
    community_traditions_lookup = build_community_tradition_lookup(
        communities_df,
        traditions_df,
        all_places_df,
    )
    tradition_specs = build_tradition_overlay_specs(
        traditions_df,
        all_places_df,
        cape_breton_places_df,
        people_counts_lookup,
    )

    main_fig = make_main_figure(cape_breton_places_df, tradition_specs)
    inset_fig = make_inset_figure(tradition_specs)

    render_html(
        main_fig,
        inset_fig,
        cape_breton_places_df,
        people_lookup,
        all_people_index,
        community_traditions_lookup,
        tradition_specs,
        output_path,
    )
    print(f"Created: {output_path}")


if __name__ == "__main__":
    main()
