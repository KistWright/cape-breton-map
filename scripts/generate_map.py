"""
Cape Breton People and Traditions Map
=====================================
------------------------

What this script is
~~~~~~~~~~~~~~~~~~~
This file is the build step for the map application. It reads the CSV source
files, turns them into cleaned lookup structures and Plotly figure specs, and
writes one standalone HTML file containing:

    - page markup
    - CSS
    - JavaScript
    - embedded Plotly library
    - embedded data exported from Python

There is no backend. After build, all interaction happens in the browser.

Current working inputs
~~~~~~~~~~~~~~~~~~~~~~
The script currently expects these files to sit beside it:

    - places.csv
    - people.csv
    - communities.csv
    - traditions.csv
    - CBscot.svg
    - SCOTcb.svg
    - map_controls.svg

Current default output
~~~~~~~~~~~~~~~~~~~~~~
The script currently writes:

    - cape_breton_people_map.html

If deployment expects index.html, either rename the file after build or change
OUTPUT_HTML near the top of this script.

What the generated HTML currently does
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The current build supports:

    - a Cape Breton main map
    - a Scotland map
    - a separate Cape Breton inset figure used when Cape Breton moves into the
      inset slot
    - map-view swap buttons to switch which geography is in the main slot
    - three side-panel modes: Places, People, Traditions
    - bilingual Gaelic / English labels throughout the UI
    - sortable lists with GD / EN sort controls
    - expandable person cards and People-tab detail controls
    - a floating traditions / inset block on the map side
    - selectable tradition overlays linking Scotland origin points to Cape
      Breton communities
    - Clear List, Restore List, Show All Traditions, and Reset Map controls
    - a popup map-controls panel loaded from map_controls.svg
    - outbound links to person pages and anchored recordings sections

How the script is organised
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Execution order is easiest to understand from main(). The broad pipeline is:

    CSVs + SVG assets
        -> cleaning / normalisation
        -> lookup building
        -> Plotly figure construction
        -> HTML/CSS/JS assembly in render_html()
        -> finished standalone HTML file

Key functions
~~~~~~~~~~~~~
Utility helpers
    cleaned_text()
    first_present_value()
    parse_number_list()
    split_bilingual_name()
    format_bilingual_plain()
    svg_path_to_data_uri()

Cleaning stage
    clean_places()
    clean_people()
    clean_communities()
    clean_traditions()

Lookup / relationship stage
    build_people_lookup()
    build_all_people_index()
    build_community_tradition_lookup()
    build_tradition_overlay_specs()

Map-building stage
    make_main_figure()
    make_cape_breton_inset_figure()
    make_inset_figure()

HTML app generation
    render_html()

Where to edit things safely
~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you need to change source-data handling:
    edit the clean_* functions and the lookup builders

If you need to change marker sizing, default centres, colours, or output file
name:
    edit the constants near the top of the file

If you need to change which traces exist or how overlays are drawn:
    edit the figure builders and build_tradition_overlay_specs()

If you need to change layout, text, CSS, or browser behaviour:
    edit render_html()

Important current implementation detail
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The browser does not create overlay traces from scratch. Python prebuilds the
traces and JavaScript mainly switches visibility, updates highlights, swaps map
slots, and re-renders list content.

Things most likely to break after edits
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - changing CSV headers without updating the cleaning functions
    - changing key names used both in Python and embedded JavaScript lookups
    - changing Plotly trace order without updating browser-side assumptions
    - changing element ids / class names in the HTML without updating the JS
    - removing the separate Cape Breton inset figure and expecting swap logic to
      continue to size markers correctly

Practical smoke test after changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
After rebuilding the HTML, check all of the following in a browser:

    1. Both map-view buttons load and swap correctly.
    2. Places, People, and Traditions tabs all open.
    3. Clicking a place shows linked people and linked traditions.
    4. Clicking a person highlights the correct Cape Breton location.
    5. Tradition overlays can be turned on and off.
    6. Clear List / Restore List / Show All Traditions work.
    7. Reset Map restores the default UI state.
    8. The map-controls popup opens and closes.
    9. Person page and recordings links resolve correctly.

Mental model for future maintenance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Treat this script as a static-app compiler:

    source tables -> cleaned data -> embedded app state -> standalone HTML app

If you are trying to find where something visible comes from, the answer is
usually one of these:

    - constants near the top of the file
    - a clean_* or build_* function
    - the HTML / CSS / JS inside render_html()

"""


import json
import base64
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

MAP_CENTER = {"lat": 46.25577950313625, "lon": -60.3}
MAP_ZOOM = 8.1

# Dedicated Cape Breton inset marker sizes. These now control the CB inset
# directly through a separate figure spec instead of relying on browser-side
# rescaling after the map swap.
CAPE_BRETON_INSET_BLUE_SIZE_BASE = 3.2
CAPE_BRETON_INSET_BLUE_SIZE_SCALE = 5.15
CAPE_BRETON_INSET_BLUE_SIZE_FLOOR = 3.0
CAPE_BRETON_INSET_BLUE_SIZE_CEILING = 15.6
CAPE_BRETON_INSET_HIGHLIGHT_OUTER_SIZE = 13
CAPE_BRETON_INSET_HIGHLIGHT_INNER_SIZE = 5
CAPE_BRETON_INSET_TRADITION_MARKER_SIZE = 10.4

SCOTLAND_CENTER = {"lat": 57.0, "lon": -5.2}
SCOTLAND_ZOOM = 5.3

ACCENT = "#8CC7EA"
TITLE_COLOUR = "#1F5F99"
BODY_TEXT = "#192930"
PANEL_BG = "#ffffff"
CARD_BG = "#ffffff"
BORDER = "#ffffff"

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


def svg_path_to_data_uri(path: Path, fallback_svg: str) -> str:
    if path.exists():
        svg_text = path.read_text(encoding="utf-8")
    else:
        svg_text = fallback_svg
    encoded = base64.b64encode(svg_text.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


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
        opacity = 0.72 + 0.24 * (counts / max_count)
    else:
        opacity = np.full(len(counts), 0.80)

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
            hoverinfo="none",
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
                hoverinfo="none",
                showlegend=False,
            )
        )

    fig.update_layout(
        map={"style": "carto-positron-nolabels", "center": MAP_CENTER, "zoom": MAP_ZOOM},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        autosize=True,
        showlegend=False,
    )
    return fig


def make_cape_breton_inset_figure(places_df: pd.DataFrame, tradition_specs: list[dict[str, Any]]) -> go.Figure:
    counts = places_df["people_count"].fillna(0).astype(float)
    sizes = np.where(
        counts > 0,
        CAPE_BRETON_INSET_BLUE_SIZE_BASE + np.sqrt(counts) * CAPE_BRETON_INSET_BLUE_SIZE_SCALE,
        CAPE_BRETON_INSET_BLUE_SIZE_FLOOR,
    )
    sizes = np.clip(sizes, CAPE_BRETON_INSET_BLUE_SIZE_FLOOR, CAPE_BRETON_INSET_BLUE_SIZE_CEILING)

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
            hoverinfo="none",
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scattermap(
            lat=[],
            lon=[],
            mode="markers",
            marker={"size": CAPE_BRETON_INSET_HIGHLIGHT_OUTER_SIZE, "color": ACCENT, "opacity": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scattermap(
            lat=[],
            lon=[],
            mode="markers",
            marker={"size": CAPE_BRETON_INSET_HIGHLIGHT_INNER_SIZE, "color": "#ffffff", "opacity": 1},
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
                marker={"size": CAPE_BRETON_INSET_TRADITION_MARKER_SIZE, "opacity": 1, "color": spec["colour"]},
                customdata=[
                    [p["place_key"], p["place_name"], p["people_count"], spec["label_plain"]]
                    for p in points
                ],
                hoverinfo="none",
                showlegend=False,
            )
        )

    fig.update_layout(
        map={"style": "carto-positron-nolabels", "center": MAP_CENTER, "zoom": MAP_ZOOM},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        autosize=True,
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
                hoverinfo="none",
                showlegend=False,
            )
        )

    fig.update_layout(
        map={
            "style": "carto-positron-nolabels",
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
        cape_breton_inset_fig: go.Figure,
        inset_fig: go.Figure,
        places_df: pd.DataFrame,
        people_lookup: dict[str, list[dict[str, str]]],
        all_people_index: list[dict[str, str]],
        community_traditions_lookup: dict[str, list[dict[str, str]]],
        tradition_specs: list[dict[str, Any]],
        output_path: Path,
) -> None:
    main_fig_dict = main_fig.to_dict()
    cape_breton_inset_fig_dict = cape_breton_inset_fig.to_dict()
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

    traditions_lookup = {
        str(spec["tradition_key"]): {
            "tradition_key": str(spec["tradition_key"]),
            "label_plain": spec["label_plain"],
            "label_gaelic": spec["label_gaelic"],
            "label_english": spec["label_english"],
            "colour": spec["colour"],
            "latitude": float(spec["scotland_point"]["latitude"]),
            "longitude": float(spec["scotland_point"]["longitude"]),
            "community_places": [
                {
                    "place_key": str(point["place_key"]),
                    "place_name": point["place_name"],
                    "place_name_gaelic": point["gaelic"],
                    "place_name_english": point["english"],
                    "latitude": float(point["latitude"]),
                    "longitude": float(point["longitude"]),
                    "people_count": int(point["people_count"]),
                }
                for point in spec["community_points"]
            ],
        }
        for spec in tradition_specs
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

    map_view_cb_svg_uri = svg_path_to_data_uri(
        Path(__file__).resolve().parent / "CBscot.svg",
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1132 910"><rect width="1132" height="910" fill="#d4d9de"/></svg>'
    )
    map_view_scotland_svg_uri = svg_path_to_data_uri(
        Path(__file__).resolve().parent / "SCOTcb.svg",
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1132 910"><rect width="1132" height="910" fill="#d4d9de"/></svg>'
    )

    place_keys_sorted = [
        str(int(row.place_key))
        for row in places_df.sort_values(
            by=["place_name", "place_name_gaelic", "place_name_english"],
            key=lambda s: s.fillna("").astype(str).str.casefold() if hasattr(s, 'fillna') else s,
        ).itertuples(index=False)
    ]

    tradition_keys_sorted = [
        str(spec["tradition_key"])
        for spec in sorted(
            tradition_specs,
            key=lambda spec: (spec["label_plain"] or "").casefold(),
        )
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
        box-sizing: border-box;
    }}

    .meta-top-item-button .person-page-link-btn {{
        width: 132px;
        max-width: 132px;
        box-sizing: border-box;
    }}
    
    .person-page-link-btn:hover,
    .recordings-link-btn:hover {{
        border-color: {ACCENT};
        color: {ACCENT};
    }}
    
    .side-panel-mode-toggle {{
        display: flex;
        gap: 4px;
        margin-bottom: 0;
        padding-top: 4px;
        flex-wrap: nowrap;
        align-items: stretch;
        justify-content: flex-start;
        position: relative;
        z-index: 3;
        overflow: visible;
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
        flex: 0 1 auto;
        width: auto;
        min-width: 0;
        max-width: 100%;
        padding: 10px 7px 9px 7px;
        border: 1px solid rgba(25, 41, 48, 0.15);
        border-bottom: 1px solid rgba(25, 41, 48, 0.12);
        background: #f4f8fb;
        color: {BODY_TEXT};
        font-size: 13px;
        font-weight: 700;
        text-transform: none;
        text-align: center;
        cursor: pointer;
        border-radius: 8px 8px 0 0;
        box-shadow: none;
        margin-bottom: 0;
        line-height: 1.1;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        white-space: nowrap;
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
        display: inline-block;
        margin: 0 0.28em;
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
        font-size: 15px;
        line-height: 1.1;
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

    .traditions-index-list {{
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
        gap: 6px;
        overflow-y: auto;
        padding-right: 2px;
    }}

    .tradition-community-list {{
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 0;
    }}

    .place-list-detail .tradition-community-pane {{
        margin-top: 4px;
    }}

    .tradition-community-btn {{
        width: 100%;
        text-align: left;
        padding: 8px 10px;
        border: 1px solid rgba(25, 41, 48, 0.08);
        border-left: 4px solid rgba(140, 199, 234, 0.55);
        border-radius: 6px;
        background: #ffffff;
        cursor: pointer;
        font: inherit;
        line-height: 1.25;
        color: {BODY_TEXT};
        transition: border-color 0.14s ease, box-shadow 0.14s ease, transform 0.14s ease, background-color 0.14s ease;
    }}

    .tradition-community-btn:hover {{
        border-color: {ACCENT};
    }}

    .tradition-community-btn.active {{
        border-left-color: {TITLE_COLOUR};
        background: rgba(31, 95, 153, 0.06);
        box-shadow: 0 2px 8px rgba(25, 41, 48, 0.08);
        transform: translateY(-1px);
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

    .main-map-slot {{
        position: relative;
        width: 100%;
        height: 100%;
        transition: opacity 180ms ease;
    }}

    .main-map-slot.map-slot-swapping,
    .combined-inset-block.map-slot-swapping {{
        opacity: 0 !important;
        visibility: hidden !important;
        pointer-events: none !important;
        transition: none !important;
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
        top: 22px;
        left: 18px;
        z-index: 1006;
        display: flex;
        align-items: flex-start;
        gap: 0;
    }}

    .overlay-toggle-btn,
    .inset-toggle-btn {{
        display: none !important;
    }}

    .overlay-empty-default {{
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        align-items: stretch;
    }}
    
    .overlay-empty-ghost {{
        flex: 1 1 auto;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 0;
        border: 1px solid rgba(25, 41, 48, 0.08);
        border-radius: 8px;
        background: rgba(25, 41, 48, 0.035);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.55);
        padding: 18px 14px;
    }}
    
    .overlay-empty-ghost-inner {{
        max-width: 220px;
        text-align: center;
    }}
    
    .overlay-empty-gaelic {{
        color: {TITLE_COLOUR};
        font-size: 12px;
        line-height: 17px;
        font-weight: 700;
        margin-bottom: 8px;
    }}
    
    .overlay-empty-english {{
        color: {ACCENT};
        font-size: 12px;
        line-height: 17px;
        font-weight: 700;
    }}
    
    .overlay-controls-hidden {{
        display: none !important;
    }}
    
    .overlay-controls-visible {{
        display: flex !important;
        flex-direction: column;
        flex: 1 1 auto;
        min-height: 0;
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

    .floating-panel-body {{
        flex: 1 1 auto;
        min-height: 0;
        overflow: hidden;
        padding: 12px 12px 12px 12px;
        display: flex;
        flex-direction: column;
    }}

    .floating-overlays {{
        right: 16px;
        top: 20px;
        bottom: 20px;
        height: auto;
        width: min(22%, 340px);
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
        transition: opacity 180ms ease;
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
        font-size: 21px;
        line-height: 22px;
        margin: 0 0 6px 0;
        text-align: center;
    }}

    .floating-panel .intro {{
        font-size: 10px;
        line-height: 14px;
        margin: 0 0 8px 0;
    }}

    #inset-map {{
        width: 100%;
        height: 100%;
        min-height: 0;
    }}

    .scot-main-selected-place-label,
    .scot-inset-selected-place-label {{
        position: absolute;
        z-index: 1004;
        display: none;
        pointer-events: none;
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid rgba(95, 167, 214, 0.45);
        border-radius: 6px;
        padding: var(--label-padding-y) var(--label-padding-x);
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        white-space: nowrap;
        transform: translate(var(--label-offset-x), -50%);
        width: max-content;
        max-width: var(--label-max-width);
        box-sizing: border-box;
        font-size: var(--label-font-size);
        line-height: var(--label-line-height);
    }}

    .scot-main-selected-place-label {{
        --label-font-size: 14.3px;
        --label-line-height: 18.2px;
        --label-padding-y: 5.2px;
        --label-padding-x: 10.4px;
        --label-offset-x: 13px;
        --label-max-width: 312px;
    }}

    .scot-inset-selected-place-label {{
        --label-font-size: 11px;
        --label-line-height: 14px;
        --label-padding-y: 4px;
        --label-padding-x: 8px;
        --label-offset-x: 10px;
        --label-max-width: 240px;
    }}

    .scot-main-selected-place-label .gaelic,
    .scot-inset-selected-place-label .gaelic {{
        color: {TITLE_COLOUR};
        font-size: var(--label-font-size);
        font-weight: 700;
        line-height: var(--label-line-height);
    }}

    .scot-main-selected-place-label .english,
    .scot-inset-selected-place-label .english {{
        color: {ACCENT};
        font-size: var(--label-font-size);
        font-weight: 700;
        line-height: var(--label-line-height);
    }}

    .scot-main-selected-place-label .separator,
    .scot-inset-selected-place-label .separator {{
        color: {ACCENT};
        font-size: var(--label-font-size);
        font-weight: 700;
        line-height: var(--label-line-height);
        margin: 0 0.15em;
    }}

    .filters-controls {{
        display: flex;
        gap: 6px;
        margin-bottom: 8px;
        flex-wrap: nowrap;
    }}
    
        .filters-controls .tiny-btn {{
        flex: 1 1 0;
        min-width: 0;
        padding: 4px 6px;
    }}
    
    .filters-controls .btn-bilingual {{
        white-space: normal;
        justify-content: center;
        text-align: center;
    }}

    .index-controls-row {{
        flex: 0 0 auto;
        display: flex;
        align-items: flex-start;
        gap: 0;
        margin: 0 0 10px 0;
        padding: 0 4px 0 2px;
        font-size: 12px;
        line-height: 16px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: rgba(25, 41, 48, 0.72);
    }}
    
    .index-controls-left {{
        display: inline-flex;
        align-items: center;
        gap: 7px;
        flex: 0 0 auto;
        min-width: 0;
    }}
    
    .index-controls-right {{
        display: inline-flex;
        align-items: center;
        justify-content: flex-end;
        gap: 6px;
        margin-left: auto;
        min-width: 0;
        flex: 1 1 auto;
        text-transform: none;
        letter-spacing: 0;
    }}

    .index-controls-left,
    .index-controls-right,
    .people-detail-controls {{
        align-self: flex-start;
    }}

    .people-detail-controls {{
        display: inline-flex;
        align-items: center;
        justify-content: flex-end;
        gap: 6px;
        margin-left: auto;
        min-width: 0;
        flex: 1 1 auto;
        text-transform: none;
        letter-spacing: 0;
    }}

    .people-detail-label {{
        display: inline-flex;
        align-items: center;
        white-space: nowrap;
        font-size: 12px;
        line-height: 16px;
        font-weight: 700;
        min-width: 0;
    }}
    
    .traditions-detail-controls {{
        display: inline-flex;
        align-items: center;
        justify-content: flex-end;
        gap: 6px;
        margin-left: auto;
        min-width: 0;
        flex: 1 1 auto;
        text-transform: none;
        letter-spacing: 0;
    }}
    
    .traditions-show-all-btn {{
        appearance: none;
        border: none;
        background: transparent;
        padding: 1px 0;
        margin: 0;
        cursor: pointer;
        font: inherit;
        display: inline-flex;
        align-items: center;
        white-space: nowrap;
        font-size: 12px;
        line-height: 16px;
        font-weight: 700;
        text-decoration: underline;
        text-decoration-color: {ACCENT};
        text-underline-offset: 2px;
    }}
    
    .traditions-show-all-btn .gaelic-dark {{
        color: {TITLE_COLOUR};
    }}
    
    .traditions-show-all-btn .english-accent,
    .traditions-show-all-btn .separator-accent {{
        color: {ACCENT};
    }}
    
    .traditions-show-all-btn .separator-accent {{
        display: inline-block;
        margin: 0 0.28em;
    }}
    
    .traditions-show-all-btn:hover {{
        opacity: 0.84;
    }}
    
    .traditions-show-all-btn:focus-visible {{
        outline: 2px solid rgba(140, 199, 234, 0.55);
        outline-offset: 3px;
        border-radius: 3px;
    }}
    
    .people-detail-label .separator-accent {{
        display: inline-block;
        margin: 0 0.28em;
    }}

    .people-detail-btn {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        padding: 0;
        border: 1px solid rgba(25, 41, 48, 0.15);
        background: #ffffff;
        color: {BODY_TEXT};
        font-size: 14px;
        font-weight: 700;
        line-height: 1;
        cursor: pointer;
        border-radius: 4px;
        flex: 0 0 auto;
    }}

    .people-detail-btn:hover {{
        border-color: {ACCENT};
        color: {ACCENT};
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

    .cb-main-selected-place-label,
    .cb-inset-selected-place-label {{
        position: absolute;
        z-index: 1002;
        display: none;
        pointer-events: none;
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid rgba(95, 167, 214, 0.45);
        border-radius: 6px;
        padding: var(--label-padding-y) var(--label-padding-x);
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        white-space: nowrap;
        transform: translate(var(--label-offset-x), -50%);
        width: max-content;
        max-width: var(--label-max-width);
        box-sizing: border-box;
        font-size: var(--label-font-size);
        line-height: var(--label-line-height);
    }}

    .cb-main-selected-place-label {{
        --label-font-size: 16px;
        --label-line-height: 18px;
        --label-padding-y: 3px;
        --label-padding-x: 10px;
        --label-offset-x: 16px;
        --label-max-width: 380px;
    }}

    .cb-inset-selected-place-label {{
        --label-font-size: 12px;
        --label-line-height: 12px;
        --label-padding-y: 0px;
        --label-padding-x: 8px;
        --label-offset-x: 12px;
        --label-max-width: 260px;
    }}

    .cb-main-selected-place-label .gaelic,
    .cb-inset-selected-place-label .gaelic {{
        color: {TITLE_COLOUR};
        font-size: var(--label-font-size);
        font-weight: 700;
        line-height: var(--label-line-height);
    }}

    .cb-main-selected-place-label .english,
    .cb-inset-selected-place-label .english {{
        color: {ACCENT};
        font-size: var(--label-font-size);
        font-weight: 700;
        line-height: var(--label-line-height);
    }}

    .cb-main-selected-place-label .separator,
    .cb-inset-selected-place-label .separator {{
        color: {ACCENT};
        font-size: var(--label-font-size);
        font-weight: 700;
        line-height: var(--label-line-height);
        margin: 0 0.2em;
    }}

    .section-title {{
        font-size: 16px;
        font-weight: 700;
        color: {ACCENT};
        line-height: 18px;
        text-transform: none;
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

    .bilingual-intro-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 14px;
        align-items: start;
        margin: 4px 0 14px 0;
        font-size: 10px;
        line-height: 15px;
    }}
    
    .bilingual-intro-grid > div {{
        min-width: 0;
    }}
    
    .bilingual-intro-grid .gaelic-dark,
    .bilingual-intro-grid .english-accent {{
        display: block;
    }}
    
    .bilingual-intro-grid .gaelic-dark {{
        text-align: left;
    }}
    
    .bilingual-intro-grid .english-accent {{
        text-align: left;
    }}

    .location-intro,
    .people-intro {{
        max-width: none;
        margin: 4px 0 14px 0;
        text-align: left;
        font-size: 12px;
        line-height: 17px;
    }}
    
    .location-intro::after,
    .people-intro::after {{
        display: none;
    }}
    
    .combined-controls-block .intro {{
        margin: 0 0 12px 0;
    }}
    
    @media (max-width: 900px) {{
        .bilingual-intro-grid {{
            grid-template-columns: 1fr;
            gap: 6px;
        }}
    }}

    .gaelic-dark {{
        color: {TITLE_COLOUR};
    }}

    .english-accent {{
        color: {ACCENT};
    }}

    .separator-accent {{
        color: {ACCENT};
    }}
    
    .btn-bilingual {{
        display: inline-flex;
        align-items: center;
        gap: 0.22em;
        white-space: nowrap;
        text-transform: none;
    }}
    
    .btn-bilingual .gaelic-dark,
    .btn-bilingual .english-accent,
    .btn-bilingual .separator-accent {{
        font-weight: 700;
        line-height: 1.2;
    }}
    
    .map-reset-btn .btn-bilingual,
    .tiny-btn .btn-bilingual {{
        text-transform: none;
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
        display: grid;
        grid-template-columns: 92px 104px 1fr;
        column-gap: 10px;
        align-items: start;
        margin-bottom: 10px;
        width: 100%;
        box-sizing: border-box;
    }}

    
    .meta-top-item {{
        min-width: 0;
        width: 100%;
    }}
    
    .meta-top-item-button {{
        width: 100%;
        display: flex;
        justify-content: flex-end;
        min-width: 0;
    }}
    
    .person-page-link-btn,
    .recordings-link-btn {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 132px;
        min-width: 132px;
        max-width: 132px;
        box-sizing: border-box;
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

    [data-slot-role="inset"] .mapboxgl-ctrl-bottom-right,
    [data-slot-role="inset"] .maplibregl-ctrl-bottom-right {{
        display: none !important;
    }}

    [data-slot-role="main"] .mapboxgl-ctrl-bottom-right,
    [data-slot-role="main"] .maplibregl-ctrl-bottom-right {{
        left: auto !important;
        right: calc(min(22%, 340px) + 28px) !important;
        bottom: 18px !important;
        display: block !important;
    }}
    
    [data-slot-role="main"] .mapboxgl-ctrl-bottom-right .mapboxgl-ctrl,
    [data-slot-role="main"] .maplibregl-ctrl-bottom-right .maplibregl-ctrl {{
        margin: 0 !important;
        padding: 0 !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }}
    
    [data-slot-role="main"] .mapboxgl-ctrl-attrib,
    [data-slot-role="main"] .maplibregl-ctrl-attrib {{
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

    [data-slot-role="main"] .mapboxgl-ctrl-attrib-button,
    [data-slot-role="main"] .maplibregl-ctrl-attrib-button {{
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
    
    [data-slot-role="main"] .mapboxgl-ctrl-attrib.mapboxgl-compact-show,
    [data-slot-role="main"] .maplibregl-ctrl-attrib.maplibregl-compact-show {{
        width: 22px !important;
        min-width: 22px !important;
        height: 22px !important;
        min-height: 22px !important;
        padding: 0 !important;
        margin: 0 !important;
    }}
    
    [data-slot-role="main"] .mapboxgl-ctrl-attrib.attrib-open .mapboxgl-ctrl-attrib-inner,
    [data-slot-role="main"] .maplibregl-ctrl-attrib.attrib-open .maplibregl-ctrl-attrib-inner {{
        position: absolute !important;
        right: 30px !important;
        left: auto !important;
        bottom: 50% !important;
        transform: translateY(50%) !important;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        white-space: nowrap !important;
    }}

    [data-slot-role="main"] .mapboxgl-ctrl-attrib:not(.attrib-open) .mapboxgl-ctrl-attrib-inner,
    [data-slot-role="main"] .maplibregl-ctrl-attrib:not(.attrib-open) .maplibregl-ctrl-attrib-inner {{
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }}

    [data-slot-role="main"] .mapboxgl-ctrl-attrib .mapboxgl-ctrl-attrib-inner,
    [data-slot-role="main"] .maplibregl-ctrl-attrib .maplibregl-ctrl-attrib-inner {{
        position: absolute;
        right: 30px;
        left: auto;
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


    .map-view-toggle {{
        position: static;
        z-index: 1006;
        pointer-events: auto;
        display: inline-flex;
        align-items: center;
    }}

    .map-view-toggle-shell {{
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 5px;
        background: rgba(31, 95, 153, 0.08);
        border: 1px solid rgba(31, 95, 153, 0.20);
        border-radius: 10px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
        backdrop-filter: blur(2px);
    }}

    .map-view-btn {{
        width: 84px;
        height: 66px;
        padding: 0;
        border: 1px solid rgba(31, 95, 153, 0.18);
        border-radius: 8px;
        background: #eaf4fb;
        box-shadow: 0 1px 4px rgba(31, 95, 153, 0.05);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        overflow: hidden;
        transition:
            border-color 0.15s ease,
            background 0.15s ease,
            box-shadow 0.15s ease,
            transform 0.15s ease,
            opacity 0.15s ease;
    }}

    .map-view-btn:hover {{
        border-color: {TITLE_COLOUR};
        background: #f4faff;
        box-shadow: 0 2px 8px rgba(31, 95, 153, 0.12);
        transform: translateY(-1px);
    }}

    .map-view-btn:focus-visible {{
        outline: none;
        border-color: {TITLE_COLOUR};
        box-shadow:
            0 0 0 2px rgba(140, 199, 234, 0.40),
            0 2px 8px rgba(31, 95, 153, 0.12);
    }}

    .map-view-btn.is-active {{
        background: #ffffff;
        border-color: rgba(31, 95, 153, 0.32);
        box-shadow:
            0 0 0 2px rgba(140, 199, 234, 0.38),
            0 2px 10px rgba(31, 95, 153, 0.12);
        transform: translateY(-1px);
    }}

    .map-view-btn:not(.is-active) {{
        opacity: 0.98;
    }}

    .map-view-btn img {{
        width: 60px;
        height: 48px;
        display: block;
        pointer-events: none;
        user-select: none;
    }}

    .map-view-btn.is-active img {{
        opacity: 1;
    }}

    .map-view-btn:not(.is-active) img {{
        opacity: 0.95;
    }}

    .map-controls-btn {{
        position: absolute;
        top: 22px;
        right: calc(min(22%, 340px) + 28px);
        left: auto;
        bottom: auto;
        width: 40px;
        height: 40px;
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
        width: 40px;
        height: 40px;
        display: block;
    }}

    .map-controls-btn svg * {{
        stroke: {TITLE_COLOUR};
    }}

    .map-controls-popup {{
        position: absolute;
        top: 12px;
        right: calc(min(22%, 340px) + 62px);
        left: auto;
        bottom: auto;
        z-index: 1007;
        width: 300px;
        max-width: calc(100% - (min(22%, 340px) + 96px));
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

    .map-reset-btn-floating {{
        position: absolute;
        left: 18px;
        right: auto;
        bottom: 18px;
        z-index: 1006;
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

    .main-map-slot {{
        height: 70vh;
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
        display: grid;
        grid-template-columns: 92px 104px 1fr;
        column-gap: 10px;
        align-items: start;
        width: 100%;
    }}
    
    .meta-top-item {{
        flex: 0 0 auto;
        width: 100%;
    }}
    
    .meta-top-item-button {{
        display: flex;
        justify-content: flex-end;
        width: 100%;
    }}

    :root {{
        --floating-panel-width: min(74vw, 300px);
        --floating-panel-min-width: 0px;
        --floating-panel-height: 42%;
    }}

    .map-view-toggle {{
        position: static;
    }}

    .map-view-toggle-shell {{
        padding: 4px;
        gap: 4px;
    }}

    .map-view-btn {{
        width: 50px;
        height: 40px;
    }}

    .map-view-btn img {{
        width: 36px;
        height: 28px;
    }}

    .map-controls-popup {{
        top: 12px;
        right: 48px;
        left: auto;
        bottom: auto;
        max-width: calc(100% - 72px);
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
    <div class="content">
        <aside class="side-panel">
            <div class="side-panel-mode-toggle">
                <button id="mode-location-btn" class="mode-btn active" type="button">
                    <span class="gaelic-dark">Àitichean</span><span class="separator-accent"> | </span><span class="english-accent">Places</span>
                </button>
                <button id="mode-all-people-btn" class="mode-btn" type="button">
                    <span class="gaelic-dark">Daoine</span><span class="separator-accent"> | </span><span class="english-accent">People</span>
                </button>
                <button id="mode-traditions-btn" class="mode-btn" type="button">
                    <span class="gaelic-dark">Dualchasan</span><span class="separator-accent"> | </span><span class="english-accent">Traditions</span>
                </button>
            </div>
            <div id="location-panel-view" class="panel-view active">
                <div class="places-index-wrap">
                    <div class="places-index-title">Cape Breton places</div>
                        <div class="info-header">
                            <div class="intro location-intro bilingual-intro-grid">
                                <div>
                                    <span class="gaelic-dark">Briog air <strong>àite</strong> air a’ mhapa no air an liosta gus na daoine agus na dualchasan e ris a shealltainn.</span>
                                </div>
                                <div>
                                    <span class="english-accent">Click a <strong>place</strong> on the map or list to show its people and traditions.</span>
                                </div>
                            </div>
                        </div>
                        <div class="index-controls-row">
                            <div class="index-controls-left">
                                <span class="place-sort-label">⇅</span>
                                <button id="sort-gaelic-btn" class="place-sort-btn sort-gd active" type="button">GD</button>
                                <span class="place-sort-separator">|</span>
                                <button id="sort-english-btn" class="place-sort-btn sort-en" type="button">EN</button>
                            </div>
                            <div class="index-controls-right"></div>
                        </div>
                    <div id="places-index-list" class="places-index-list"></div>
                </div>
            </div>

            <div id="all-people-panel-view" class="panel-view">
                <div class="info-header">
                    <div class="intro people-intro bilingual-intro-grid">
                        <div>
                            <span class="gaelic-dark">Briog air <strong>ainm</strong> gus fiosrachadh mun neach agus an t-àite aca air a’ mhapa fhaicinn.</span>
                        </div>
                        <div>
                            <span class="english-accent">Click on a <strong>name</strong> to view the person details and their map location.</span>
                        </div>
                    </div>
                </div>
                    <div class="index-controls-row">
                        <div class="index-controls-left">
                            <span class="place-sort-label">⇅</span>
                            <button id="people-sort-gaelic-btn" class="place-sort-btn sort-gd active" type="button">GD</button>
                            <span class="place-sort-separator">|</span>
                            <button id="people-sort-english-btn" class="place-sort-btn sort-en" type="button">EN</button>
                        </div>
                    
                        <div class="index-controls-right people-detail-controls">
                            <span class="people-detail-label">
                                <span class="gaelic-dark">Mion-fhiosrachadh</span><span class="separator-accent"> | </span><span class="english-accent">Detail</span>
                            </span>
                            <button id="people-detail-less-btn" class="people-detail-btn" type="button" aria-label="Less detail">&lt;</button>
                            <button id="people-detail-more-btn" class="people-detail-btn" type="button" aria-label="More detail">&gt;</button>
                        </div>
                    </div>
                <div id="all-people-list" class="people-list"></div>
            </div>

            <div id="traditions-panel-view" class="panel-view">
                <div class="places-index-wrap">
                    <div class="places-index-title">Traditions</div>
                        <div class="info-header">
                            <div class="intro location-intro bilingual-intro-grid">
                                <div>
                                    <span class="gaelic-dark">Briog air <strong>dualchas</strong> gus coimhearsnachdan Cheap Breatainn co-cheangailte ris a shealltainn.</span>
                                </div>
                                <div>
                                    <span class="english-accent">Click on a <strong>tradition</strong> to show the associated Cape Breton communities.</span>
                                </div>
                            </div>
                        </div>
                        <div class="index-controls-row">
                        <div class="index-controls-left">
                            <span class="place-sort-label">⇅</span>
                            <button id="tradition-sort-gaelic-btn" class="place-sort-btn sort-gd active" type="button">GD</button>
                            <span class="place-sort-separator">|</span>
                            <button id="tradition-sort-english-btn" class="place-sort-btn sort-en" type="button">EN</button>
                        </div>
                        <div class="index-controls-right traditions-detail-controls">
                            <button id="show-all-cb-btn" class="traditions-show-all-btn" type="button">
                                <span class="gaelic-dark">Seall na Dualchasan</span><span class="separator-accent"> | </span><span class="english-accent">Show all Traditions</span>
                            </button>
                        </div>
                    </div>
                    <div id="traditions-index-list" class="traditions-index-list"></div>
                </div>
            </div>
        </aside>

        <div class="map-panel">
            <div class="top-map-buttons">
                <div class="map-view-toggle" aria-label="Map view toggle">
                    <div class="map-view-toggle-shell" role="group" aria-label="Map view">
                        <button id="map-view-cb-btn" class="map-view-btn is-active" type="button" aria-pressed="true" aria-label="Cape Breton main map with Scotland inset" title="Cape Breton main map with Scotland inset">
                            <img src="{map_view_cb_svg_uri}" alt="">
                        </button>
                        <button id="map-view-scotland-btn" class="map-view-btn" type="button" aria-pressed="false" aria-label="Scotland main map with Cape Breton inset" title="Scotland main map with Cape Breton inset">
                            <img src="{map_view_scotland_svg_uri}" alt="">
                        </button>
                    </div>
                </div>
                
            </div>

            <div id="floating-overlays" class="floating-panel floating-overlays combined-traditions-panel">
                <div class="floating-panel-body combined-traditions-body">
                    <div id="inset-map-slot" class="combined-inset-block" data-slot-role="inset" data-map-identity="scotland">
                        <div id="scot-inset-selected-place-label" class="scot-inset-selected-place-label"></div>
                        <div id="inset-map"></div>
                    </div>
                
                    <div id="overlay-empty-default" class="overlay-empty-default">
                        <div class="overlay-empty-ghost">
                            <div class="overlay-empty-ghost-inner">
                                <div class="overlay-empty-gaelic">Tagh àite no neach bho na tabaichean air an làimh dheis, no briog air àite air a’ mhapa, gus na dualchasan co-cheangailte ris a shealltainn; tagh 'Seall na Dualchasan' bhon taba Dualchasan gus na dualchasan uile a tha co-cheangailte ri Ceap Breatainn fhaicinn.</div>
                                <div class="overlay-empty-english">Select a place or person from the tabs on the right, or click a place on the map, to load their associated traditions; select 'Show all Traditions' from the Traditions tab to view all traditions linked to Cape Breton.</div>
                            </div>
                        </div>
                    </div>
                
                    <div id="combined-controls-block" class="combined-controls-block overlay-controls-hidden">
                        <div class="intro bilingual-intro-grid">
                            <div>
                                <span class="gaelic-dark">Tagh no dì-thagh dualchasan gus na coimhearsnachdan co-cheangailte.</span>
                            </div>
                            <div>
                                <span class="english-accent">Select or deselect traditions to highlight associated communities.</span>
                            </div>
                        </div>   
                        <div class="filters-controls">
                            <button id="clear-all-traditions" class="tiny-btn" type="button">
                                <span class="btn-bilingual">
                                    <span class="gaelic-dark">Glan an Liosta</span>
                                    <span class="separator-accent">|</span>
                                    <span class="english-accent">Clear List</span>
                                </span>
                            </button>
                        
                            <button id="restore-all-traditions" class="tiny-btn" type="button">
                                <span class="btn-bilingual">
                                    <span class="gaelic-dark">Aisig an Liosta</span>
                                    <span class="separator-accent">|</span>
                                    <span class="english-accent">Restore List</span>
                                </span>
                            </button>
                        </div>
                        <div id="overlay-list" class="overlay-list"></div>
                    </div>
                </div>
            </div>

            <button id="reset-map-btn" class="map-reset-btn map-reset-btn-floating" type="button">
                <span class="btn-bilingual">
                    <span class="gaelic-dark">Ùraich am Mapa</span>                       
                    <span class="separator-accent">|</span>
                    <span class="english-accent">Reset Map</span>
                </span>
            </button>
                
<button id="map-controls-btn" class="map-controls-btn" type="button" aria-label="Show map controls">
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <g transform="translate(0 2.6)">
            <!-- mouse -->
            <rect x="4.5" y="2.5" width="8" height="13" rx="4" stroke-width="1.8"/>
            <line x1="8.5" y1="2.5" x2="8.5" y2="6.5" stroke-width="1.8" stroke-linecap="round"/>
        </g>

        <g transform="translate(0 0.8)">
            <!-- question mark -->
            <path d="M15.4 8.2
                     C15.4 6.9 16.3 6.1 17.6 6.1
                     C18.8 6.1 19.7 6.9 19.7 8.0
                     C19.7 8.8 19.3 9.4 18.4 10.0
                     C17.6 10.5 17.2 11.0 17.2 11.8"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"/>
            <circle cx="17.2" cy="14.8" r="0.9" fill="{TITLE_COLOUR}" stroke="none"/>
        </g>
    </svg>
</button>


            <div id="map-controls-popup" class="map-controls-popup hidden" aria-hidden="true">
                <button id="map-controls-popup-close" class="map-controls-popup-close" type="button" aria-label="Close map controls"></button>
                {map_controls_svg}
            </div>

            <div id="main-map-slot" class="main-map-slot" data-slot-role="main" data-map-identity="cape-breton">
                <div id="cb-main-selected-place-label" class="cb-main-selected-place-label"></div>
                <div id="cb-inset-selected-place-label" class="cb-inset-selected-place-label"></div>
                <div id="scot-main-selected-place-label" class="scot-main-selected-place-label"></div>
                <div id="map"></div>
            </div>
        </div>
    </div>
</div>

<script>
    const capeBretonMainFigureSpec = {json.dumps(main_fig_dict, ensure_ascii=False)};
    const capeBretonInsetFigureSpec = {json.dumps(cape_breton_inset_fig_dict, ensure_ascii=False)};
    const scotlandFigureSpec = {json.dumps(inset_fig_dict, ensure_ascii=False)};
    const placesLookup = {json.dumps(places_lookup, ensure_ascii=False)};
    const peopleByPlace = {json.dumps(people_lookup, ensure_ascii=False)};
    const allPeopleIndex = {json.dumps(all_people_index, ensure_ascii=False)};
    const overlayControlsAll = {json.dumps(overlay_controls_all, ensure_ascii=False)};
    const CAPE_BRETON_BLUE_TRACE_INDEXES = [0];
    const CAPE_BRETON_HIGHLIGHT_TRACE_INDEXES = [1, 2];
    const CAPE_BRETON_TRADITION_TRACE_INDEXES = [...new Set(overlayControlsAll.map((item) => Number(item.main_trace_index)).filter((value) => Number.isFinite(value)))];
    const SCOTLAND_HIGHLIGHT_TRACE_INDEXES = [0, 1];
    const SCOTLAND_TRADITION_TRACE_INDEXES = [...new Set(overlayControlsAll.map((item) => Number(item.inset_trace_index)).filter((value) => Number.isFinite(value)))];
    const traditionsLookup = {json.dumps(traditions_lookup, ensure_ascii=False)};
    const INITIAL_CENTER = {json.dumps(MAP_CENTER)};
    const INITIAL_ZOOM = {MAP_ZOOM};
    const INITIAL_BOUNDS = {{
        north: 47.05595763626309,
        south: 45.45560137000942,
        west: -61.61803600597501,
        east: -59.64582664072555
    }};
    const SCOTLAND_DEFAULT_INSET_CENTER = {{lat: 57.0, lon: -5.2}};
    const SCOTLAND_DEFAULT_INSET_ZOOM = 5.3;
    const SCOTLAND_MAIN_BOUNDS = {{
        north: 58.72183467850293,
        south: 55.240843103743444,
        east: -1.6161098569124013,
        west: -7.969807341730092
    }};
    const SCOTLAND_MAIN_CENTER = {{
        lat: ((SCOTLAND_MAIN_BOUNDS.north + SCOTLAND_MAIN_BOUNDS.south) / 2) + 0.10,
        lon: ((SCOTLAND_MAIN_BOUNDS.east + SCOTLAND_MAIN_BOUNDS.west) / 2) + 1.20
    }};
    const SCOTLAND_MAIN_ZOOM = 6.55;
    const CAPE_BRETON_DEFAULT_INSET_CENTER = {{lat: 46.27, lon: -60.63}};
    const CAPE_BRETON_DEFAULT_INSET_ZOOM = 6.70;
    const allPlaceKeys = {json.dumps(place_keys_sorted, ensure_ascii=False)};
    const allTraditionKeys = {json.dumps(tradition_keys_sorted, ensure_ascii=False)};
    const MAP_VIEW_MODE_CAPE_BRETON_MAIN = 'cape-breton-main';
    const MAP_VIEW_MODE_SCOTLAND_MAIN = 'scotland-main';
    const MAP_SLOT_MAIN = 'main';
    const MAP_SLOT_INSET = 'inset';
    const CAPE_BRETON_FIGURE_VARIANT_MAIN = 'main';
    const CAPE_BRETON_FIGURE_VARIANT_INSET = 'inset';
    const PLOTLY_MAP_CONFIG = {{
        responsive: true,
        displaylogo: false,
        displayModeBar: false
    }};
    const PLOTLY_SCOTLAND_MAP_CONFIG = {{
        responsive: true,
        displaylogo: false,
        displayModeBar: false,
        staticPlot: false
    }};
    const MAP_STYLE_PRESETS = {{
        'cape-breton': {{
            main: {{
                labelScale: 1,
                labelBoxScale: 1
            }},
            inset: {{
                labelScale: 1,
                labelBoxScale: 1
            }}
        }},
        scotland: {{
            main: {{
                traditionMarkerScale: 0.40,
                highlightMarkerScale: 2.0,
                labelScale: 1.3,
                labelBoxScale: 1.3
            }},
            inset: {{
                traditionMarkerScale: 1,
                highlightMarkerScale: 1,
                labelScale: 1,
                labelBoxScale: 1
            }}
        }}
    }};
    const CAPE_BRETON_MAIN_LABEL_STYLE = {{
        fontSize: 14,
        lineHeight: 14,
        paddingY: 6,
        paddingX: 6,
        offsetX: 13,
        maxWidth: 380
    }};
    const CAPE_BRETON_INSET_LABEL_STYLE = {{
        fontSize: 12,
        lineHeight: 12,
        paddingY: 4,
        paddingX: 4,
        offsetX: 10,
        maxWidth: 260
    }};
    const SCOTLAND_MAIN_LABEL_STYLE = {{
        fontSize: 14,
        lineHeight: 14,
        paddingY: 6,
        paddingX: 6,
        offsetX: 13,
        maxWidth: 312
    }};
    const SCOTLAND_INSET_LABEL_STYLE = {{
        fontSize: 12,
        lineHeight: 12,
        paddingY: 4,
        paddingX: 4,
        offsetX: 10,
        maxWidth: 240
    }};
    let CAPE_BRETON_BASE_TRACE_MARKER_SIZES = null;
    let SCOTLAND_BASE_TRACE_MARKER_SIZES = null;
    let CAPE_BRETON_BASE_MARKER_OPACITY = null;


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
        const buttons = capeBretonMapDiv.querySelectorAll('.modebar-btn');
        buttons.forEach((btn) => {{
            const title = btn.getAttribute('data-title') || '';
            if (!/download plot as a png/i.test(title)) {{
                btn.style.display = 'none';
            }}
        }});

        const groups = capeBretonMapDiv.querySelectorAll('.modebar-group');
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

    function scrollItemToTopWithinPane(item, pane) {{
        if (!item || !pane) return;
        const paneRect = pane.getBoundingClientRect();
        const itemRect = item.getBoundingClientRect();
        const targetTop = pane.scrollTop + (itemRect.top - paneRect.top) - 6;
        pane.scrollTo({{ top: Math.max(0, targetTop), behavior: 'auto' }});
    }}

    function setActivePlaceInList(placeKey = null, options = {{}}) {{
        renderPlacesIndex(placeKey);
        if (!placeKey || !placesIndexList) return;
        const activeItem = placesIndexList.querySelector('.place-list-item.active');
        if (!activeItem) return;
        if (options.alignToTop !== false) {{
            scrollItemToTopWithinPane(activeItem, placesIndexList);
        }} else if (typeof activeItem.scrollIntoView === 'function') {{
            activeItem.scrollIntoView({{ block: 'nearest' }});
        }}
    }}

    function setActiveTraditionInList(traditionKey = null, options = {{}}) {{
        renderTraditionsIndex(traditionKey, currentTraditionCommunityKey);
        if (!traditionKey || !traditionsIndexList) return;
        const activeItem = traditionsIndexList.querySelector('.place-list-item.active');
        if (!activeItem) return;
        if (options.alignToTop !== false) {{
            scrollItemToTopWithinPane(activeItem, traditionsIndexList);
        }} else if (typeof activeItem.scrollIntoView === 'function') {{
            activeItem.scrollIntoView({{ block: 'nearest' }});
        }}
    }}

    function setPlaceSort(mode) {{
        currentPlaceSort = mode === 'english' ? 'english' : 'gaelic';
        setActivePlaceInList(currentLocationPlaceKey);
    }}

    let currentTraditionSort = 'gaelic';

    function getTraditionSortLabel(traditionKey, mode = currentTraditionSort) {{
        const tradition = traditionsLookup[String(traditionKey)] || {{}};
        if (mode === 'english') {{
            return (tradition.label_english || tradition.label_gaelic || tradition.label_plain || '').trim();
        }}
        return (tradition.label_gaelic || tradition.label_english || tradition.label_plain || '').trim();
    }}

    function getSortedTraditionKeys(mode = currentTraditionSort) {{
        return allTraditionKeys.slice().sort((a, b) => {{
            const aLabel = getTraditionSortLabel(a, mode).toLocaleLowerCase();
            const bLabel = getTraditionSortLabel(b, mode).toLocaleLowerCase();
            return aLabel.localeCompare(bLabel) || String(a).localeCompare(String(b));
        }});
    }}

    function updateTraditionSortButtons() {{
        if (traditionSortGaelicBtn) traditionSortGaelicBtn.classList.toggle('active', currentTraditionSort === 'gaelic');
        if (traditionSortEnglishBtn) traditionSortEnglishBtn.classList.toggle('active', currentTraditionSort === 'english');
    }}

    function renderTraditionInlineDetail(traditionKey, activeCommunityKey = null) {{
        const tradition = traditionsLookup[String(traditionKey)];
        if (!tradition) {{
            return '<div class="place-list-detail"><div class="empty">No data found for that tradition.</div></div>';
        }}

        const communities = (tradition.community_places || []).slice().sort((a, b) => {{
            const aLabel = currentTraditionSort === 'english'
                ? (a.place_name_english || a.place_name_gaelic || a.place_name || '').toLocaleLowerCase()
                : (a.place_name_gaelic || a.place_name_english || a.place_name || '').toLocaleLowerCase();
            const bLabel = currentTraditionSort === 'english'
                ? (b.place_name_english || b.place_name_gaelic || b.place_name || '').toLocaleLowerCase()
                : (b.place_name_gaelic || b.place_name_english || b.place_name || '').toLocaleLowerCase();
            return aLabel.localeCompare(bLabel) || String(a.place_key).localeCompare(String(b.place_key));
        }});

        if (!communities.length) {{
            return '<div class="place-list-detail"><div class="empty">No Cape Breton communities are linked to this tradition.</div></div>';
        }}

        const items = communities.map((community) => {{
            const isActive = String(activeCommunityKey || '') === String(community.place_key);
            const labelHtml = formatBilingualHtml(
                community.place_name_gaelic || '',
                community.place_name_english || '',
                'english-highlight-place'
            );
            const peopleCount = Number(community.people_count || 0);
            return `
                <button class="tradition-community-btn${{isActive ? ' active' : ''}}" type="button" data-tradition-community-key="${{escapeHtml(String(community.place_key))}}">
                    <span class="place-list-name">${{labelHtml}}</span>
                    <span class="place-list-meta">Informants: ${{peopleCount}}</span>
                </button>`;
        }}).join('');

        return `<div class="place-list-detail"><div class="informants-pane tradition-community-pane"><div class="tradition-community-list">${{items}}</div></div></div>`;
    }}

    function renderTraditionsIndex(activeTraditionKey = null, activeCommunityKey = null) {{
        if (!traditionsIndexList) return;

        updateTraditionSortButtons();

        const html = getSortedTraditionKeys().map((traditionKey) => {{
            const tradition = traditionsLookup[String(traditionKey)] || {{}};
            const isActive = String(activeTraditionKey || '') === String(traditionKey);
            const labelHtml = formatBilingualHtml(
                tradition.label_gaelic || '',
                tradition.label_english || '',
                'english-highlight-place'
            );
            const communityCount = Array.isArray(tradition.community_places) ? tradition.community_places.length : 0;

            return `
                <div class="place-list-item${{isActive ? ' active' : ''}}" data-tradition-key="${{escapeHtml(String(traditionKey))}}">
                    <button class="place-list-btn${{isActive ? ' active' : ''}}" type="button" data-tradition-key="${{escapeHtml(String(traditionKey))}}">
                        <span class="place-list-name">${{labelHtml}}</span>
                        <span class="place-list-meta">Communities: ${{communityCount}}</span>
                    </button>
                    ${{isActive ? renderTraditionInlineDetail(traditionKey, activeCommunityKey) : ''}}
                </div>`;
        }}).join('');

        traditionsIndexList.innerHTML = html;

        traditionsIndexList.querySelectorAll('button[data-tradition-key]').forEach((btn) => {{
            btn.addEventListener('click', function() {{
                const traditionKey = this.dataset.traditionKey;
                const isAlreadyActive = String(currentTraditionPanelKey || '') === String(traditionKey);
                if (isAlreadyActive) {{
                    clearTraditionPanelSelection(true);
                    return;
                }}
                activateTradition(traditionKey, {{ source: 'list' }});
            }});
        }});

        traditionsIndexList.querySelectorAll('[data-tradition-community-key]').forEach((btn) => {{
            btn.addEventListener('click', function(event) {{
                event.stopPropagation();
                const communityKey = this.dataset.traditionCommunityKey;
                const isAlreadyActive = String(currentTraditionCommunityKey || '') === String(communityKey);
                if (isAlreadyActive) {{
                    currentTraditionCommunityKey = null;
                    renderTraditionsIndex(currentTraditionPanelKey, null);
                    clearSelectionRing();
                    hideSelectedPlaceLabel();
                    return;
                }}
                activateTraditionCommunityPlace(communityKey);
            }});
        }});
    }}

    function setTraditionSort(mode) {{
        currentTraditionSort = mode === 'english' ? 'english' : 'gaelic';
        renderTraditionsIndex(currentTraditionPanelKey, currentTraditionCommunityKey);
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
        currentTraditionPanelKey = null;
        currentTraditionCommunityKey = null;
        renderPlacesIndex(null);
        renderTraditionsIndex(null, null);
    }}

    function clearTraditionPanelSelection(preserveMode = false) {{
        currentTraditionPanelKey = null;
        currentTraditionCommunityKey = null;
        renderTraditionsIndex(null, null);
        clearSelectionRing();
        hideSelectedPlaceLabel();
        clearAllTraditionsAndControls();
        if (preserveMode) {{
            setSidePanelMode('traditions');
        }}
    }}

    function clearActivePlaceSelection() {{
        currentLocationPlaceKey = null;
        currentTraditionPanelKey = null;
        currentTraditionCommunityKey = null;
        renderPlacesIndex(null);
        renderTraditionsIndex(null, null);
        clearSelectedPerson({{ restoreActivePlace: false }});
        clearAllTraditionsAndControls();
    }}

    function clearSelectionRing() {{
        Plotly.restyle(capeBretonMapDiv, {{lat: [[], []], lon: [[], []]}}, [1, 2]);
    }}

    function clearInsetSelectionRing() {{
        Plotly.restyle(scotlandMapDiv, {{lat: [[], []], lon: [[], []]}}, [0, 1]);
    }}

    function buildInsetSelectedPlaceLabelHtml(customPlaceName) {{
        const [gaelic, english] = String(customPlaceName || '').includes('|')
            ? String(customPlaceName || '').split('|', 2).map((s) => s.trim())
            : [String(customPlaceName || '').trim(), ''];

        if (gaelic && english) {{
            return `<span class="gaelic">${{escapeHtml(gaelic)}}</span><span class="separator"> | </span><span class="english">${{escapeHtml(english)}}</span>`;
        }}
        if (english) {{
            return `<span class="english">${{escapeHtml(english)}}</span>`;
        }}
        return `<span class="gaelic">${{escapeHtml(gaelic)}}</span>`;
    }}

    function getActiveCapeBretonPlaceLabelState() {{
        return capeBretonHoveredPlaceState || capeBretonSelectedPlaceState;
    }}

    function getActiveInsetPlaceLabelState() {{
        return scotlandHoveredPlaceState || scotlandSelectedPlaceState;
    }}

    function getActiveScotlandLabelElement() {{
        return getSlotRoleForMapIdentity('scotland') === MAP_SLOT_INSET
            ? scotlandInsetSelectedPlaceLabel
            : scotlandMainSelectedPlaceLabel;
    }}

    function hideInactiveScotlandLabelElements() {{
        const activeLabelElement = getActiveScotlandLabelElement();
        [scotlandMainSelectedPlaceLabel, scotlandInsetSelectedPlaceLabel].forEach((labelElement) => {{
            if (!labelElement || labelElement === activeLabelElement) return;
            labelElement.style.display = 'none';
            labelElement.innerHTML = '';
        }});
    }}

    function getActiveCapeBretonLabelElement() {{
        return getSlotRoleForMapIdentity('cape-breton') === MAP_SLOT_INSET
            ? capeBretonInsetSelectedPlaceLabel
            : capeBretonMainSelectedPlaceLabel;
    }}

    function hideInactiveCapeBretonLabelElements() {{
        const activeLabelElement = getActiveCapeBretonLabelElement();
        [capeBretonMainSelectedPlaceLabel, capeBretonInsetSelectedPlaceLabel].forEach((labelElement) => {{
            if (!labelElement || labelElement === activeLabelElement) return;
            labelElement.style.display = 'none';
            labelElement.innerHTML = '';
        }});
    }}

    function hideSelectedPlaceLabel() {{
        capeBretonSelectedPlaceState = null;
        capeBretonHoveredPlaceState = null;
        [capeBretonMainSelectedPlaceLabel, capeBretonInsetSelectedPlaceLabel].forEach((labelElement) => {{
            if (!labelElement) return;
            labelElement.style.display = 'none';
            labelElement.innerHTML = '';
        }});
    }}

    function hideInsetSelectedPlaceLabel() {{
        scotlandSelectedPlaceState = null;
        scotlandHoveredPlaceState = null;
        [scotlandMainSelectedPlaceLabel, scotlandInsetSelectedPlaceLabel].forEach((labelElement) => {{
            if (!labelElement) return;
            labelElement.style.display = 'none';
            labelElement.innerHTML = '';
        }});
    }}

    function clearCapeBretonHoverPlaceLabel() {{
        capeBretonHoveredPlaceState = null;
        positionSelectedPlaceLabel();
    }}

    function clearInsetHoverPlaceLabel() {{
        scotlandHoveredPlaceState = null;
        positionInsetSelectedPlaceLabel();
    }}

    function positionSelectedPlaceLabel() {{
        const activeState = getActiveCapeBretonPlaceLabelState();
        const activeLabelElement = getActiveCapeBretonLabelElement();
        hideInactiveCapeBretonLabelElements();
        if (!activeState || !capeBretonSubplotMap || typeof capeBretonSubplotMap.project !== 'function') {{
            if (activeLabelElement) activeLabelElement.style.display = 'none';
            return;
        }}

        const projected = capeBretonSubplotMap.project([activeState.lon, activeState.lat]);
        if (!projected) {{
            return;
        }}

        if (!activeLabelElement) return;
        activeLabelElement.innerHTML = activeState.html;
        activeLabelElement.style.left = `${{projected.x}}px`;
        activeLabelElement.style.top = `${{projected.y}}px`;
        activeLabelElement.style.display = 'block';
    }}

    function positionInsetSelectedPlaceLabel() {{
        const activeState = getActiveInsetPlaceLabelState();
        const activeLabelElement = getActiveScotlandLabelElement();
        hideInactiveScotlandLabelElements();
        if (!activeState || !scotlandSubplotMap || typeof scotlandSubplotMap.project !== 'function') {{
            if (activeLabelElement) activeLabelElement.style.display = 'none';
            return;
        }}

        const projected = scotlandSubplotMap.project([activeState.lon, activeState.lat]);
        if (!projected) {{
            return;
        }}

        if (!activeLabelElement) return;
        activeLabelElement.innerHTML = activeState.html;
        activeLabelElement.style.left = `${{projected.x}}px`;
        activeLabelElement.style.top = `${{projected.y}}px`;
        activeLabelElement.style.display = 'block';
    }}

    function showSelectedPlaceLabel(place, lat, lon) {{
        capeBretonSelectedPlaceState = {{
            lat: lat,
            lon: lon,
            html: buildSelectedPlaceLabelHtml(place),
        }};
        positionSelectedPlaceLabel();
    }}

    function showCapeBretonHoverPlaceLabel(place, lat, lon) {{
        capeBretonHoveredPlaceState = {{
            lat: lat,
            lon: lon,
            html: buildSelectedPlaceLabelHtml(place),
        }};
        positionSelectedPlaceLabel();
    }}

    function showInsetSelectedPlaceLabel(customPlaceName, lat, lon) {{
        scotlandSelectedPlaceState = {{
            lat: lat,
            lon: lon,
            html: buildInsetSelectedPlaceLabelHtml(customPlaceName),
        }};
        positionInsetSelectedPlaceLabel();
    }}

    function showInsetHoverPlaceLabel(customPlaceName, lat, lon) {{
        scotlandHoveredPlaceState = {{
            lat: lat,
            lon: lon,
            html: buildInsetSelectedPlaceLabelHtml(customPlaceName),
        }};
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

        const updatePromises = [];
        if (mainTraceIndexes.length) {{
            updatePromises.push(Plotly.restyle(capeBretonMapDiv, {{visible: mainVisible}}, mainTraceIndexes));
        }}
        if (insetTraceIndexes.length) {{
            updatePromises.push(Plotly.restyle(scotlandMapDiv, {{visible: insetVisible}}, insetTraceIndexes));
        }}
        Promise.all(updatePromises).then(() => {{
            syncCapeBretonBaseMarkerVisualPriority(checkedValue && keySet.size > 0);
            return Promise.all([
                Plotly.redraw(capeBretonMapDiv),
                Plotly.redraw(scotlandMapDiv)
            ]);
        }});
    }}

    function updateOverlayListActionButton() {{
        if (!clearAllTraditionsBtn || !restoreAllTraditionsBtn) return;
    
        const checkboxes = [...document.querySelectorAll('.tradition-toggle')];
        const hasList = checkboxes.length > 0;
        const anyChecked = checkboxes.some((checkbox) => checkbox.checked);
        const anyUnchecked = checkboxes.some((checkbox) => !checkbox.checked);
    
        clearAllTraditionsBtn.disabled = !hasList || !anyChecked;
        restoreAllTraditionsBtn.disabled = !hasList || !anyUnchecked;
    }}  

    function clearAllTraditionsAndControls() {{
        currentOverlayTraditionKeys = [];
        overlayListCleared = false;
        setAllTraditionsVisibleByKeys([], false);
        renderOverlayControls([]);
        updateOverlayListActionButton();
        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();
    }}

    function showAllTraditionsInCapeBreton() {{
        currentLocationPlaceKey = null;
        currentTraditionPanelKey = null;
        currentTraditionCommunityKey = null;
        resetInfoPanel();
        clearSelectedPerson();
        clearSelectionRing();
        hideSelectedPlaceLabel();
        const allKeys = overlayControlsAll.map((item) => String(item.tradition_key));
        currentOverlayTraditionKeys = allKeys.slice();
        overlayListCleared = false;
        renderPlacesIndex(null);
        renderTraditionsIndex(null, null);
        renderOverlayControls(currentOverlayTraditionKeys, true);
        setAllTraditionsVisibleByKeys(currentOverlayTraditionKeys, true);
        updateOverlayListActionButton();
        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();
    }}
        
    function fitCapeBretonMapToInitialBounds() {{
        forceResetMapViewport(
            capeBretonMapDiv,
            INITIAL_CENTER,
            INITIAL_ZOOM,
            () => capeBretonSubplotMap || capeBretonMapDiv?._fullLayout?.map?._subplot?.map || capeBretonMapDiv?._fullLayout?.mapbox?._subplot?.map || null,
            capeBretonViewportRequestTracker
        );
    }}

    function fitCapeBretonMapToLegacyInitialBounds() {{
        if (!capeBretonSubplotMap || typeof capeBretonSubplotMap.fitBounds !== 'function') return;
    
        capeBretonSubplotMap.fitBounds(
            [
                [INITIAL_BOUNDS.west, INITIAL_BOUNDS.south],
                [INITIAL_BOUNDS.east, INITIAL_BOUNDS.north]
            ],
            {{
                padding: 0,
                duration: 0
            }}
        );
    }}

    function forceResetMapViewport(mapDiv, center, zoom, getSubplotMap = null, requestTracker = null) {{
        if (!mapDiv) return;

        const requestId = requestTracker ? ++requestTracker.value : null;
        const isStale = () => requestTracker && requestId !== requestTracker.value;
        const centerArray = [center.lon, center.lat];
        const relayoutPayload = {{
            'map.center': {{lat: center.lat, lon: center.lon}},
            'map.zoom': zoom
        }};

        const applyDomMapReset = () => {{
            const subplotMap = typeof getSubplotMap === 'function' ? getSubplotMap() : null;
            if (!subplotMap) return;
            if (typeof subplotMap.jumpTo === 'function') {{
                subplotMap.jumpTo({{ center: centerArray, zoom: zoom }});
            }} else if (typeof subplotMap.easeTo === 'function') {{
                subplotMap.easeTo({{ center: centerArray, zoom: zoom, duration: 0 }});
            }}
            if (typeof subplotMap.resize === 'function') {{
                subplotMap.resize();
            }}
        }};

        const applyReset = () => {{
            if (isStale()) return;
            Plotly.relayout(mapDiv, relayoutPayload);
            applyDomMapReset();
        }};

        applyReset();
        requestAnimationFrame(() => {{
            if (isStale()) return;
            applyReset();
            requestAnimationFrame(() => {{
                if (isStale()) return;
                applyReset();
                window.setTimeout(() => {{
                    if (isStale()) return;
                    applyReset();
                }}, 0);
            }});
        }});
    }}

    const scotlandViewportRequestTracker = {{ value: 0 }};
    const capeBretonViewportRequestTracker = {{ value: 0 }};

    function fitScotlandMapToMainBounds() {{
        forceResetMapViewport(
            scotlandMapDiv,
            SCOTLAND_MAIN_CENTER,
            SCOTLAND_MAIN_ZOOM,
            () => scotlandSubplotMap || scotlandMapDiv?._fullLayout?.map?._subplot?.map || scotlandMapDiv?._fullLayout?.mapbox?._subplot?.map || null,
            scotlandViewportRequestTracker
        );
    }}

    function fitScotlandMapToInsetDefault() {{
        forceResetMapViewport(
            scotlandMapDiv,
            SCOTLAND_DEFAULT_INSET_CENTER,
            SCOTLAND_DEFAULT_INSET_ZOOM,
            () => scotlandSubplotMap || scotlandMapDiv?._fullLayout?.map?._subplot?.map || scotlandMapDiv?._fullLayout?.mapbox?._subplot?.map || null,
            scotlandViewportRequestTracker
        );
    }}

    function fitCapeBretonMapToInsetDefault() {{
        forceResetMapViewport(
            capeBretonMapDiv,
            CAPE_BRETON_DEFAULT_INSET_CENTER,
            CAPE_BRETON_DEFAULT_INSET_ZOOM,
            () => capeBretonSubplotMap || capeBretonMapDiv?._fullLayout?.map?._subplot?.map || capeBretonMapDiv?._fullLayout?.mapbox?._subplot?.map || null,
            capeBretonViewportRequestTracker
        );
    }}

    function resetMapsForCurrentViewMode() {{
        if (currentMapViewMode === MAP_VIEW_MODE_SCOTLAND_MAIN) {{
            fitScotlandMapToMainBounds();
            fitCapeBretonMapToInsetDefault();
        }} else {{
            fitCapeBretonMapToInitialBounds();
            fitScotlandMapToInsetDefault();
        }}
    }}
        
    function resetMainMapAndPanels() {{
        clearActivePlaceSelection();
        resetMapsForCurrentViewMode();
        scheduleMapViewResize();
    }}
    
    let currentOverlayTraditionKeys = [];
    let overlayListCleared = false;

    function showLocationTraditionsSection(placeKey) {{
        const place = placesLookup[String(placeKey)];
        currentTraditionPanelKey = null;
        currentTraditionCommunityKey = null;
        renderTraditionsIndex(null, null);

        if (!place) {{
            currentOverlayTraditionKeys = [];
            overlayListCleared = false;
            renderOverlayControls([]);
            setAllTraditionsVisibleByKeys([], false);
            updateOverlayListActionButton();
            clearInsetSelectionRing();
            hideInsetSelectedPlaceLabel();
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
    
    }}

    function renderPlace(placeKey) {{
        const place = placesLookup[String(placeKey)];

        if (!place) {{
            renderPlacesIndex(null);
            renderOverlayControls([]);
            return;
        }}

        currentLocationPlaceKey = String(placeKey);
        setActivePlaceInList(currentLocationPlaceKey, {{ alignToTop: true }});
        requestAnimationFrame(() => setActivePlaceInList(currentLocationPlaceKey, {{ alignToTop: true }}));
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
            capeBretonMapDiv,
            {{ lat: [[place.latitude], [place.latitude]], lon: [[place.longitude], [place.longitude]] }},
            [1, 2]
        );
        showSelectedPlaceLabel(place, place.latitude, place.longitude);
    }}

    function activateTradition(traditionKey, options = {{}}) {{
        const tradition = traditionsLookup[String(traditionKey)];
        if (!tradition) return;

        clearSelectedPerson({{ restoreActivePlace: false }});
        currentLocationPlaceKey = null;
        currentTraditionPanelKey = String(traditionKey);
        currentTraditionCommunityKey = null;
        renderPlacesIndex(null);
        setSidePanelMode('traditions');
        setActiveTraditionInList(currentTraditionPanelKey, {{ alignToTop: true }});
        requestAnimationFrame(() => setActiveTraditionInList(currentTraditionPanelKey, {{ alignToTop: true }}));

        currentOverlayTraditionKeys = [String(traditionKey)];
        overlayListCleared = false;
        renderOverlayControls(currentOverlayTraditionKeys, true);
        setAllTraditionsVisibleByKeys(currentOverlayTraditionKeys, true);
        updateOverlayListActionButton();

        clearSelectionRing();
        hideSelectedPlaceLabel();

        Plotly.restyle(
            scotlandMapDiv,
            {{
                lat: [[tradition.latitude], [tradition.latitude]],
                lon: [[tradition.longitude], [tradition.longitude]]
            }},
            [0, 1]
        );
        showInsetSelectedPlaceLabel(tradition.label_plain, tradition.latitude, tradition.longitude);

    }}

    function activateTraditionCommunityPlace(placeKey) {{
        const place = placesLookup[String(placeKey)];
        if (!place || !currentTraditionPanelKey) return;

        clearSelectedPerson({{ restoreActivePlace: false }});
        currentLocationPlaceKey = null;
        currentTraditionCommunityKey = String(placeKey);
        renderTraditionsIndex(currentTraditionPanelKey, currentTraditionCommunityKey);

        Plotly.restyle(
            capeBretonMapDiv,
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
            overlayList.innerHTML = '';
            showOverlayDefaultMessage();
            updateOverlayListActionButton();
            return;
        }}
    
        showOverlayControls();
        overlayList.innerHTML = items.map((item) => buildOverlayRowHtml(item, checkedState)).join('');
        updateOverlayListActionButton();
    
        document.querySelectorAll('.tradition-toggle').forEach((checkbox) => {{
            checkbox.addEventListener('change', function() {{
                const mainTraceIndex = Number(this.dataset.mainTraceIndex);
                const insetTraceIndex = Number(this.dataset.insetTraceIndex);
                const visibleValue = this.checked;
        
                Promise.all([
                    Plotly.restyle(capeBretonMapDiv, {{visible: visibleValue}}, [mainTraceIndex]),
                    Plotly.restyle(scotlandMapDiv, {{visible: visibleValue}}, [insetTraceIndex])
                ]).then(() => {{
                    const anyChecked = [...document.querySelectorAll('.tradition-toggle')].some((checkbox) => checkbox.checked);
                    syncCapeBretonBaseMarkerVisualPriority(anyChecked);
                    return Promise.all([
                        Plotly.redraw(capeBretonMapDiv),
                        Plotly.redraw(scotlandMapDiv)
                    ]);
                }});
        
                clearInsetSelectionRing();
                hideInsetSelectedPlaceLabel();
                updateOverlayListActionButton();
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

        Promise.all([
            Plotly.restyle(capeBretonMapDiv, {{visible: visibleValues}}, mainTraceIndexes),
            Plotly.restyle(scotlandMapDiv, {{visible: visibleValues}}, insetTraceIndexes)
        ]).then(() => {{
            syncCapeBretonBaseMarkerVisualPriority(isVisible && checkboxes.length > 0);
            return Promise.all([
                Plotly.redraw(capeBretonMapDiv),
                Plotly.redraw(scotlandMapDiv)
            ]);
        }});
        
        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();
    }}

    function setOverlayPanelVisibility(isVisible) {{
        floatingOverlays.classList.remove('hidden');
    }}

    function setInsetPanelVisibility(isVisible) {{
        if (floatingInset) {{
            floatingInset.classList.remove('hidden');
        }}
        setTimeout(() => {{
            Plotly.Plots.resize(scotlandMapDiv);
        }}, 0);
    }}

    function setSidePanelMode(mode) {{
        const showLocation = mode === 'location';
        const showAllPeople = mode === 'all';
        const showTraditions = mode === 'traditions';

        locationPanelView.classList.toggle('active', showLocation);
        allPeoplePanelView.classList.toggle('active', showAllPeople);
        traditionsPanelView.classList.toggle('active', showTraditions);

        modeLocationBtn.classList.toggle('active', showLocation);
        modeAllPeopleBtn.classList.toggle('active', showAllPeople);
        modeTraditionsBtn.classList.toggle('active', showTraditions);

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
                capeBretonMapDiv,
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
                    capeBretonMapDiv,
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
            capeBretonMapDiv,
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
    }}

    function getAllPeopleLetterGroups() {{
        return Array.from(document.querySelectorAll('#all-people-list details.people-letter-group'));
    }}

    function getOpenPeopleLetterGroups() {{
        return getAllPeopleLetterGroups().filter((group) => group.open);
    }}

    function getAllPeopleCards() {{
        return Array.from(document.querySelectorAll('#all-people-list details.person-card'));
    }}

    function getVisiblePeopleCards() {{
        const cards = [];
        getOpenPeopleLetterGroups().forEach((group) => {{
            cards.push(...Array.from(group.querySelectorAll('details.person-card')));
        }});
        return cards;
    }}

    function closeOpenPersonCards() {{
        getAllPeopleCards().forEach((card) => {{
            card.open = false;
        }});
    }}

    function openVisiblePeopleCards() {{
        getVisiblePeopleCards().forEach((card) => {{
            card.open = true;
        }});
    }}

    function openAllPeopleCards() {{
        getAllPeopleCards().forEach((card) => {{
            card.open = true;
        }});
    }}

    function openAllLetterGroupsPreservingCards() {{
        getAllPeopleLetterGroups().forEach((group) => {{
            group.open = true;
        }});
    }}

    function collapseAllLetterGroups() {{
        getAllPeopleLetterGroups().forEach((group) => {{
            group.open = false;
        }});
        closeOpenPersonCards();
    }}

    function increasePeopleDetail() {{
        const allGroups = getAllPeopleLetterGroups();
        const openGroups = getOpenPeopleLetterGroups();
        const allCards = getAllPeopleCards();
        const visibleCards = getVisiblePeopleCards();

        const allGroupsOpen = allGroups.length > 0 && openGroups.length === allGroups.length;
        const visibleCardsHaveClosed = visibleCards.some((card) => !card.open);
        const allCardsOpen = allCards.length > 0 && allCards.every((card) => card.open);

        if (!allGroupsOpen) {{
            if (openGroups.length > 0 && visibleCardsHaveClosed) {{
                openVisiblePeopleCards();
                return;
            }}
            openAllLetterGroupsPreservingCards();
            return;
        }}

        if (!allCardsOpen) {{
            openAllPeopleCards();
        }}
    }}

    function decreasePeopleDetail() {{
        const allCards = getAllPeopleCards();
        const hasAnyOpenCards = allCards.some((card) => card.open);
        if (hasAnyOpenCards) {{
            closeOpenPersonCards();
            return;
        }}

        const openGroups = getOpenPeopleLetterGroups();
        if (openGroups.length > 0) {{
            collapseAllLetterGroups();
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
    
    const capeBretonMapDiv = document.getElementById('map');
    const scotlandMapDiv = document.getElementById('inset-map');
    const resetBtn = document.getElementById('reset-map-btn');
    const showAllCbBtn = document.getElementById('show-all-cb-btn');
    const capeBretonMainSelectedPlaceLabel = document.getElementById('cb-main-selected-place-label');
    const capeBretonInsetSelectedPlaceLabel = document.getElementById('cb-inset-selected-place-label');
    const scotlandMainSelectedPlaceLabel = document.getElementById('scot-main-selected-place-label');
    const scotlandInsetSelectedPlaceLabel = document.getElementById('scot-inset-selected-place-label');
    const overlayList = document.getElementById('overlay-list');
    const clearAllTraditionsBtn = document.getElementById('clear-all-traditions');
    const restoreAllTraditionsBtn = document.getElementById('restore-all-traditions');
    const floatingOverlays = document.getElementById('floating-overlays');
    const floatingInset = document.getElementById('floating-inset');
    const placesIndexList = document.getElementById('places-index-list');
    const sortGaelicBtn = document.getElementById('sort-gaelic-btn');
    const sortEnglishBtn = document.getElementById('sort-english-btn');
    const peopleSortGaelicBtn = document.getElementById('people-sort-gaelic-btn');
    const peopleSortEnglishBtn = document.getElementById('people-sort-english-btn');
    const traditionSortGaelicBtn = document.getElementById('tradition-sort-gaelic-btn');
    const traditionSortEnglishBtn = document.getElementById('tradition-sort-english-btn');
    const traditionsIndexList = document.getElementById('traditions-index-list');
    const overlayEmptyDefault = document.getElementById('overlay-empty-default');
    const combinedControlsBlock = document.getElementById('combined-controls-block');
    const mainMapSlot = document.getElementById('main-map-slot');
    const insetMapSlot = document.getElementById('inset-map-slot');
    const mapViewCapeBretonBtn = document.getElementById('map-view-cb-btn');
    const mapViewScotlandBtn = document.getElementById('map-view-scotland-btn');

    let currentMapViewMode = MAP_VIEW_MODE_CAPE_BRETON_MAIN;
    let currentCapeBretonFigureVariant = CAPE_BRETON_FIGURE_VARIANT_MAIN;

    function getCurrentMainMapIdentity() {{
        return currentMapViewMode === MAP_VIEW_MODE_SCOTLAND_MAIN ? 'scotland' : 'cape-breton';
    }}

    function getCurrentInsetMapIdentity() {{
        return currentMapViewMode === MAP_VIEW_MODE_SCOTLAND_MAIN ? 'cape-breton' : 'scotland';
    }}

    function syncMapSlotMetadata() {{
        if (mainMapSlot) {{
            mainMapSlot.dataset.slotRole = 'main';
            mainMapSlot.dataset.mapIdentity = getCurrentMainMapIdentity();
        }}
        if (insetMapSlot) {{
            insetMapSlot.dataset.slotRole = 'inset';
            insetMapSlot.dataset.mapIdentity = getCurrentInsetMapIdentity();
        }}
    }}

    function syncMapViewToggleUi() {{
        const isCapeBretonMain = currentMapViewMode === MAP_VIEW_MODE_CAPE_BRETON_MAIN;
        if (mapViewCapeBretonBtn) {{
            mapViewCapeBretonBtn.classList.toggle('is-active', isCapeBretonMain);
            mapViewCapeBretonBtn.setAttribute('aria-pressed', isCapeBretonMain ? 'true' : 'false');
        }}
        if (mapViewScotlandBtn) {{
            mapViewScotlandBtn.classList.toggle('is-active', !isCapeBretonMain);
            mapViewScotlandBtn.setAttribute('aria-pressed', !isCapeBretonMain ? 'true' : 'false');
        }}
    }}

    function getMapStylePreset(mapIdentity, slotRole) {{
        const mapPresets = MAP_STYLE_PRESETS[mapIdentity] || {{}};
        return mapPresets[slotRole] || {{ markerScale: 1, labelScale: 1 }};
    }}

    function getSlotRoleForMapIdentity(mapIdentity) {{
        return getCurrentMainMapIdentity() === mapIdentity ? MAP_SLOT_MAIN : MAP_SLOT_INSET;
    }}

    function decodePlotlyTypedArray(value) {{
        if (!value || typeof value !== 'object' || Array.isArray(value) || ArrayBuffer.isView(value)) {{
            return value;
        }}
        const dtype = typeof value.dtype === 'string' ? value.dtype.toLowerCase() : '';
        const bdata = typeof value.bdata === 'string' ? value.bdata : '';
        if (!dtype || !bdata) return value;

        const binary = atob(bdata);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) {{
            bytes[i] = binary.charCodeAt(i);
        }}

        let typedArray;
        switch (dtype) {{
            case 'f8': typedArray = new Float64Array(bytes.buffer); break;
            case 'f4': typedArray = new Float32Array(bytes.buffer); break;
            case 'i4': typedArray = new Int32Array(bytes.buffer); break;
            case 'u4': typedArray = new Uint32Array(bytes.buffer); break;
            case 'i2': typedArray = new Int16Array(bytes.buffer); break;
            case 'u2': typedArray = new Uint16Array(bytes.buffer); break;
            case 'i1': typedArray = new Int8Array(bytes.buffer); break;
            case 'u1': typedArray = new Uint8Array(bytes.buffer); break;
            default: return value;
        }}
        return Array.from(typedArray);
    }}

    function normaliseMarkerSizeValue(sizeValue) {{
        const decodedValue = decodePlotlyTypedArray(sizeValue);
        if (Array.isArray(decodedValue)) {{
            return decodedValue.map((item) => Number.isFinite(Number(item)) ? Number(item) : item);
        }}
        if (ArrayBuffer.isView(decodedValue)) {{
            return Array.from(decodedValue).map((item) => Number.isFinite(Number(item)) ? Number(item) : item);
        }}
        const numericSize = Number(decodedValue);
        return Number.isFinite(numericSize) ? numericSize : decodedValue;
    }}

    function captureBaseTraceMarkerSizes(mapDiv) {{
        if (!mapDiv || !Array.isArray(mapDiv.data)) return [];
        return mapDiv.data.map((trace) => (
            trace && trace.marker && trace.marker.size != null
                ? normaliseMarkerSizeValue(trace.marker.size)
                : null
        ));
    }}

    function ensureBaseTraceMarkerSizesCaptured() {{
        if (!CAPE_BRETON_BASE_TRACE_MARKER_SIZES) {{
            CAPE_BRETON_BASE_TRACE_MARKER_SIZES = captureBaseTraceMarkerSizes(capeBretonMapDiv);
        }}
        if (!SCOTLAND_BASE_TRACE_MARKER_SIZES) {{
            SCOTLAND_BASE_TRACE_MARKER_SIZES = captureBaseTraceMarkerSizes(scotlandMapDiv);
        }}
        if (CAPE_BRETON_BASE_MARKER_OPACITY == null && capeBretonMapDiv && Array.isArray(capeBretonMapDiv.data) && capeBretonMapDiv.data[0] && capeBretonMapDiv.data[0].marker) {{
            CAPE_BRETON_BASE_MARKER_OPACITY = normaliseMarkerSizeValue(capeBretonMapDiv.data[0].marker.opacity);
        }}
    }}

    function refreshCapeBretonBaseMarkersFromCurrentFigure() {{
        CAPE_BRETON_BASE_TRACE_MARKER_SIZES = captureBaseTraceMarkerSizes(capeBretonMapDiv);
        if (capeBretonMapDiv && Array.isArray(capeBretonMapDiv.data) && capeBretonMapDiv.data[0] && capeBretonMapDiv.data[0].marker) {{
            CAPE_BRETON_BASE_MARKER_OPACITY = normaliseMarkerSizeValue(capeBretonMapDiv.data[0].marker.opacity);
        }}
    }}

    function getCapeBretonFigureVariantForCurrentSlot() {{
        return getSlotRoleForMapIdentity('cape-breton') === MAP_SLOT_INSET
            ? CAPE_BRETON_FIGURE_VARIANT_INSET
            : CAPE_BRETON_FIGURE_VARIANT_MAIN;
    }}

    function getCapeBretonFigureSpecForVariant(figureVariant) {{
        return figureVariant === CAPE_BRETON_FIGURE_VARIANT_INSET
            ? capeBretonInsetFigureSpec
            : capeBretonMainFigureSpec;
    }}

    function captureCapeBretonMapUiState() {{
        const state = {{
            baseOpacity: null,
            highlightLatLon: [],
            traditionVisibility: []
        }};
        if (!capeBretonMapDiv || !Array.isArray(capeBretonMapDiv.data) || !capeBretonMapDiv.data.length) return state;

        const baseTrace = capeBretonMapDiv.data[0];
        if (baseTrace && baseTrace.marker && baseTrace.marker.opacity != null) {{
            state.baseOpacity = normaliseMarkerSizeValue(baseTrace.marker.opacity);
        }}

        [1, 2].forEach((traceIndex) => {{
            const trace = capeBretonMapDiv.data[traceIndex];
            state.highlightLatLon.push({{
                traceIndex,
                lat: Array.isArray(trace?.lat) ? [...trace.lat] : [],
                lon: Array.isArray(trace?.lon) ? [...trace.lon] : []
            }});
        }});

        state.traditionVisibility = CAPE_BRETON_TRADITION_TRACE_INDEXES.map((traceIndex) => {{
            const trace = capeBretonMapDiv.data[traceIndex];
            return {{
                traceIndex,
                visible: !!(trace && trace.visible === true)
            }};
        }});

        return state;
    }}

    function restoreCapeBretonMapUiState(state) {{
        if (!capeBretonMapDiv || !state) return Promise.resolve();
        const updatePromises = [];

        if (state.baseOpacity != null) {{
            updatePromises.push(Plotly.restyle(capeBretonMapDiv, {{ 'marker.opacity': [state.baseOpacity] }}, [0]));
        }}

        (state.highlightLatLon || []).forEach((item) => {{
            updatePromises.push(
                Plotly.restyle(
                    capeBretonMapDiv,
                    {{ lat: [item.lat || []], lon: [item.lon || []] }},
                    [item.traceIndex]
                )
            );
        }});

        const visibilityTraceIndexes = [];
        const visibilityValues = [];
        (state.traditionVisibility || []).forEach((item) => {{
            visibilityTraceIndexes.push(item.traceIndex);
            visibilityValues.push(item.visible);
        }});
        if (visibilityTraceIndexes.length) {{
            updatePromises.push(Plotly.restyle(capeBretonMapDiv, {{ visible: visibilityValues }}, visibilityTraceIndexes));
        }}

        return updatePromises.length ? Promise.all(updatePromises) : Promise.resolve();
    }}

    function ensureCapeBretonFigureVariantForCurrentSlot() {{
        const nextVariant = getCapeBretonFigureVariantForCurrentSlot();
        if (!capeBretonMapDiv || !Array.isArray(capeBretonMapDiv.data) || !capeBretonMapDiv.data.length) {{
            currentCapeBretonFigureVariant = nextVariant;
            return Promise.resolve();
        }}
        if (currentCapeBretonFigureVariant === nextVariant) {{
            return Promise.resolve();
        }}

        const capturedState = captureCapeBretonMapUiState();
        const nextFigureSpec = getCapeBretonFigureSpecForVariant(nextVariant);

        return Plotly.react(capeBretonMapDiv, nextFigureSpec.data, nextFigureSpec.layout, PLOTLY_MAP_CONFIG).then(() => {{
            currentCapeBretonFigureVariant = nextVariant;
            refreshCapeBretonBaseMarkersFromCurrentFigure();
            capeBretonSubplotMap =
                capeBretonMapDiv?._fullLayout?.map?._subplot?.map ||
                capeBretonMapDiv?._fullLayout?.mapbox?._subplot?.map ||
                null;
            return restoreCapeBretonMapUiState(capturedState);
        }});
    }}

    function scaleOpacityValue(opacityValue, scale) {{
        if (Array.isArray(opacityValue)) {{
            return opacityValue.map((item) => Number.isFinite(Number(item)) ? Math.max(0.08, Math.min(1, Number(item) * scale)) : item);
        }}
        const numericOpacity = Number(opacityValue);
        return Number.isFinite(numericOpacity) ? Math.max(0.08, Math.min(1, numericOpacity * scale)) : opacityValue;
    }}

    function syncCapeBretonBaseMarkerVisualPriority(forceAnyOverlayVisible = null) {{
        if (CAPE_BRETON_BASE_MARKER_OPACITY == null) return;
        const anyOverlayVisible = (typeof forceAnyOverlayVisible === 'boolean')
            ? forceAnyOverlayVisible
            : (Array.isArray(overlayControlsAll) && overlayControlsAll.some((item) => {{
                const trace = capeBretonMapDiv?.data?.[item.main_trace_index];
                return !!(trace && trace.visible === true);
            }}));
        const nextOpacity = anyOverlayVisible
            ? scaleOpacityValue(CAPE_BRETON_BASE_MARKER_OPACITY, 0.42)
            : CAPE_BRETON_BASE_MARKER_OPACITY;
        Plotly.restyle(capeBretonMapDiv, {{ 'marker.opacity': [nextOpacity] }}, [0]);
    }}

    function scaleMarkerSizeValue(sizeValue, scale) {{
        if (Array.isArray(sizeValue)) {{
            return sizeValue.map((item) => Number.isFinite(Number(item)) ? Number(item) * scale : item);
        }}
        const numericSize = Number(sizeValue);
        return Number.isFinite(numericSize) ? numericSize * scale : sizeValue;
    }}

    function buildScaledMarkerPayloadForTraceIndexes(baseTraceMarkerSizes, traceIndexes, scale) {{
        const payloadTraceIndexes = [];
        const scaledSizes = [];
        (traceIndexes || []).forEach((traceIndex) => {{
            const baseSize = baseTraceMarkerSizes?.[traceIndex];
            if (baseSize == null) return;
            payloadTraceIndexes.push(traceIndex);
            scaledSizes.push(scaleMarkerSizeValue(baseSize, scale));
        }});
        return {{ traceIndexes: payloadTraceIndexes, scaledSizes }};
    }}

    function applyScaledMarkerPresetForTraceIndexes(mapDiv, baseTraceMarkerSizes, traceIndexes, scale) {{
        if (!mapDiv || !Array.isArray(mapDiv.data) || !mapDiv.data.length) return;
        const payload = buildScaledMarkerPayloadForTraceIndexes(baseTraceMarkerSizes, traceIndexes, scale);
        if (!payload.traceIndexes.length) return;
        Plotly.restyle(mapDiv, {{ 'marker.size': payload.scaledSizes }}, payload.traceIndexes);
    }}

    function applyScaledLabelPreset(labelElement, baseStyle, textScale, boxScale = null) {{
        if (!labelElement || !baseStyle) return;
        const effectiveBoxScale = Number.isFinite(Number(boxScale)) ? Number(boxScale) : textScale;
        labelElement.style.setProperty('--label-font-size', `${{baseStyle.fontSize * textScale}}px`);
        labelElement.style.setProperty('--label-line-height', `${{baseStyle.lineHeight * textScale}}px`);
        labelElement.style.setProperty('--label-padding-y', `${{baseStyle.paddingY * effectiveBoxScale}}px`);
        labelElement.style.setProperty('--label-padding-x', `${{baseStyle.paddingX * effectiveBoxScale}}px`);
        labelElement.style.setProperty('--label-offset-x', `${{baseStyle.offsetX * effectiveBoxScale}}px`);
        labelElement.style.setProperty('--label-max-width', `${{baseStyle.maxWidth * effectiveBoxScale}}px`);
    }}

    function applyMapSlotStylePresets() {{
        ensureBaseTraceMarkerSizesCaptured();
        const capeBretonSlotRole = getSlotRoleForMapIdentity('cape-breton');
        const scotlandSlotRole = getSlotRoleForMapIdentity('scotland');
        const capeBretonPreset = getMapStylePreset('cape-breton', capeBretonSlotRole);
        const scotlandPreset = getMapStylePreset('scotland', scotlandSlotRole);

        applyScaledMarkerPresetForTraceIndexes(scotlandMapDiv, SCOTLAND_BASE_TRACE_MARKER_SIZES, SCOTLAND_HIGHLIGHT_TRACE_INDEXES, scotlandPreset.highlightMarkerScale ?? 1);
        applyScaledMarkerPresetForTraceIndexes(scotlandMapDiv, SCOTLAND_BASE_TRACE_MARKER_SIZES, SCOTLAND_TRADITION_TRACE_INDEXES, scotlandPreset.traditionMarkerScale ?? 1);

        const capeBretonLabelBaseStyle = (
            capeBretonSlotRole === MAP_SLOT_MAIN
                ? CAPE_BRETON_MAIN_LABEL_STYLE
                : CAPE_BRETON_INSET_LABEL_STYLE
        );
        applyScaledLabelPreset(capeBretonMainSelectedPlaceLabel, CAPE_BRETON_MAIN_LABEL_STYLE, 1, 1);
        applyScaledLabelPreset(capeBretonInsetSelectedPlaceLabel, CAPE_BRETON_INSET_LABEL_STYLE, 1, 1);
        applyScaledLabelPreset(scotlandMainSelectedPlaceLabel, SCOTLAND_MAIN_LABEL_STYLE, 1, 1);
        applyScaledLabelPreset(scotlandInsetSelectedPlaceLabel, SCOTLAND_INSET_LABEL_STYLE, 1, 1);
    }}

    function setMapSlotSwapMask(isActive) {{
        if (mainMapSlot) {{
            mainMapSlot.classList.toggle('map-slot-swapping', !!isActive);
        }}
        if (insetMapSlot) {{
            insetMapSlot.classList.toggle('map-slot-swapping', !!isActive);
        }}
    }}

    function scheduleMapViewResize(afterResizeCallback = null) {{
        requestAnimationFrame(() => {{
            requestAnimationFrame(() => {{
                Plotly.Plots.resize(capeBretonMapDiv);
                Plotly.Plots.resize(scotlandMapDiv);
                if (capeBretonSubplotMap && typeof capeBretonSubplotMap.resize === 'function') {{
                    capeBretonSubplotMap.resize();
                }}
                if (scotlandSubplotMap && typeof scotlandSubplotMap.resize === 'function') {{
                    scotlandSubplotMap.resize();
                }}
                positionSelectedPlaceLabel();
                positionInsetSelectedPlaceLabel();
                wireMainMapAttributionToggle();
                if (typeof afterResizeCallback === 'function') {{
                    afterResizeCallback();
                }}
            }});
        }});
    }}

    function settleMapsAfterSwap(releaseMask = false) {{
        scheduleMapViewResize(() => {{
            resetMapsForCurrentViewMode();
            requestAnimationFrame(() => {{
                scheduleMapViewResize(() => {{
                    resetMapsForCurrentViewMode();
                    requestAnimationFrame(() => {{
                        positionSelectedPlaceLabel();
                        positionInsetSelectedPlaceLabel();
                        wireMainMapAttributionToggle();
                        if (releaseMask) {{
                            window.setTimeout(() => {{
                                setMapSlotSwapMask(false);
                            }}, 120);
                        }}
                    }});
                }});
            }});
        }});
    }}

    function applyMapViewMode(options = {{}}) {{
        const {{
            resetInsetAfterSwap = false,
            useTransitionMask = false
        }} = options;

        const mainIdentity = getCurrentMainMapIdentity();
        const insetIdentity = getCurrentInsetMapIdentity();

        const performSwap = () => {{
            if (mainMapSlot) {{
                if (mainIdentity === 'scotland') {{
                    mainMapSlot.appendChild(scotlandMainSelectedPlaceLabel);
                    mainMapSlot.appendChild(scotlandMapDiv);
                }} else {{
                    mainMapSlot.appendChild(capeBretonMainSelectedPlaceLabel);
                    mainMapSlot.appendChild(capeBretonMapDiv);
                }}
            }}

            if (insetMapSlot) {{
                if (insetIdentity === 'cape-breton') {{
                    insetMapSlot.appendChild(capeBretonInsetSelectedPlaceLabel);
                    insetMapSlot.appendChild(capeBretonMapDiv);
                }} else {{
                    insetMapSlot.appendChild(scotlandInsetSelectedPlaceLabel);
                    insetMapSlot.appendChild(scotlandMapDiv);
                }}
            }}

            ensureCapeBretonFigureVariantForCurrentSlot().then(() => {{
                syncMapSlotMetadata();
                syncMapViewToggleUi();
                applyMapSlotStylePresets();
                resetMapsForCurrentViewMode();
                if (resetInsetAfterSwap) {{
                    settleMapsAfterSwap(useTransitionMask);
                }} else {{
                    scheduleMapViewResize(() => {{
                        resetMapsForCurrentViewMode();
                        requestAnimationFrame(() => {{
                            resetMapsForCurrentViewMode();
                            positionSelectedPlaceLabel();
                            positionInsetSelectedPlaceLabel();
                            wireMainMapAttributionToggle();
                            if (useTransitionMask) {{
                                window.setTimeout(() => {{
                                    setMapSlotSwapMask(false);
                                }}, 120);
                            }}
                        }});
                    }});
                }}
            }});
        }};

        if (useTransitionMask) {{
            setMapSlotSwapMask(true);
            requestAnimationFrame(() => {{
                requestAnimationFrame(() => {{
                    performSwap();
                }});
            }});
            return;
        }}

        performSwap();
    }}

    function setCurrentMapViewMode(nextMode) {{
        const normalizedMode = nextMode === MAP_VIEW_MODE_SCOTLAND_MAIN
            ? MAP_VIEW_MODE_SCOTLAND_MAIN
            : MAP_VIEW_MODE_CAPE_BRETON_MAIN;

        if (currentMapViewMode === normalizedMode) {{
            applyMapViewMode({{ resetInsetAfterSwap: true, useTransitionMask: false }});
            return;
        }}

        currentMapViewMode = normalizedMode;
        applyMapViewMode({{ resetInsetAfterSwap: true, useTransitionMask: true }});
    }}

    function wireMapViewToggleButtons() {{
        if (mapViewCapeBretonBtn) {{
            mapViewCapeBretonBtn.addEventListener('click', () => {{
                setCurrentMapViewMode(MAP_VIEW_MODE_CAPE_BRETON_MAIN);
            }});
        }}

        if (mapViewScotlandBtn) {{
            mapViewScotlandBtn.addEventListener('click', () => {{
                setCurrentMapViewMode(MAP_VIEW_MODE_SCOTLAND_MAIN);
            }});
        }}
    }}

    applyMapViewMode();
    wireMapViewToggleButtons();

    function showOverlayDefaultMessage() {{
        if (overlayEmptyDefault) overlayEmptyDefault.style.display = 'flex';
        if (combinedControlsBlock) {{
            combinedControlsBlock.classList.remove('overlay-controls-visible');
            combinedControlsBlock.classList.add('overlay-controls-hidden');
        }}
    }}
    
    function showOverlayControls() {{
        if (overlayEmptyDefault) overlayEmptyDefault.style.display = 'none';
        if (combinedControlsBlock) {{
            combinedControlsBlock.classList.remove('overlay-controls-hidden');
            combinedControlsBlock.classList.add('overlay-controls-visible');
        }}
    }}

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
    if (traditionSortGaelicBtn) {{
        traditionSortGaelicBtn.addEventListener('click', () => setTraditionSort('gaelic'));
    }}
    if (traditionSortEnglishBtn) {{
        traditionSortEnglishBtn.addEventListener('click', () => setTraditionSort('english'));
    }}
    const modeLocationBtn = document.getElementById('mode-location-btn');
    const modeAllPeopleBtn = document.getElementById('mode-all-people-btn');
    const modeTraditionsBtn = document.getElementById('mode-traditions-btn');
    const locationPanelView = document.getElementById('location-panel-view');
    const allPeoplePanelView = document.getElementById('all-people-panel-view');
    const traditionsPanelView = document.getElementById('traditions-panel-view');
    const allPeopleList = document.getElementById('all-people-list');
    const peopleDetailLessBtn = document.getElementById('people-detail-less-btn');
    const peopleDetailMoreBtn = document.getElementById('people-detail-more-btn');
    const mapControlsBtn = document.getElementById('map-controls-btn');
    const mapControlsPopup = document.getElementById('map-controls-popup');
    const mapControlsPopupClose = document.getElementById('map-controls-popup-close');

    let capeBretonSelectedPlaceState = null;
    let capeBretonHoveredPlaceState = null;
    let scotlandSelectedPlaceState = null;
    let scotlandHoveredPlaceState = null;
    let capeBretonSubplotMap = null;
    let scotlandSubplotMap = null;
    let suppressNextInsetBackgroundClick = false;
    let currentLocationPlaceKey = null;
    let currentTraditionPanelKey = null;
    let currentTraditionCommunityKey = null;
    let capeBretonMapResizeFrame = null;
    let hasSeenInitialResizeObservation = false;

    function refitMapsAfterResize() {{
        if (capeBretonMapResizeFrame) {{
            cancelAnimationFrame(capeBretonMapResizeFrame);
        }}
    
        capeBretonMapResizeFrame = requestAnimationFrame(function() {{
            Plotly.Plots.resize(capeBretonMapDiv);
            Plotly.Plots.resize(scotlandMapDiv);
            resetMapsForCurrentViewMode();
            positionSelectedPlaceLabel();
            positionInsetSelectedPlaceLabel();
        }});
    }}

    function getCurrentMainMapDiv() {{
        return getCurrentMainMapIdentity() === 'scotland' ? scotlandMapDiv : capeBretonMapDiv;
    }}

    function wireMainMapAttributionToggle() {{
        const currentMainMapDiv = getCurrentMainMapDiv();
        if (!currentMainMapDiv) return;

        const attrib =
            currentMainMapDiv.querySelector('.mapboxgl-ctrl-attrib, .maplibregl-ctrl-attrib');
    
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
        capeBretonMapDiv,
        capeBretonMainFigureSpec.data,
        capeBretonMainFigureSpec.layout,
        PLOTLY_MAP_CONFIG
    ).then(function() {{
        wireMainMapAttributionToggle();
        wireMapControlsPopup();
        Plotly.Plots.resize(capeBretonMapDiv);

        Plotly.newPlot(
            scotlandMapDiv,
            scotlandFigureSpec.data,
            scotlandFigureSpec.layout,
            PLOTLY_SCOTLAND_MAP_CONFIG
        ).then(function() {{
            syncMapSlotMetadata();
            syncMapViewToggleUi();
            currentCapeBretonFigureVariant = CAPE_BRETON_FIGURE_VARIANT_MAIN;
            ensureBaseTraceMarkerSizesCaptured();
            applyMapSlotStylePresets();
            renderPlacesIndex(null);
            renderTraditionsIndex(null, null);
            renderOverlayControls([]);
            updateOverlayListActionButton();
            showOverlayDefaultMessage();
            setOverlayPanelVisibility(true);
            setInsetPanelVisibility(true);
            setSidePanelMode('location');
            resetInfoPanel();

            setTimeout(() => {{
                renderAllPeopleList();
            }}, 0);

            scotlandSubplotMap =
                scotlandMapDiv?._fullLayout?.map?._subplot?.map ||
                scotlandMapDiv?._fullLayout?.mapbox?._subplot?.map ||
                null;

            if (scotlandSubplotMap && typeof scotlandSubplotMap.on === 'function') {{
                scotlandSubplotMap.on('move', function() {{
                    positionInsetSelectedPlaceLabel();
                }});

                scotlandSubplotMap.on('zoom', function() {{
                    positionInsetSelectedPlaceLabel();
                }});

                scotlandSubplotMap.on('resize', function() {{
                    positionInsetSelectedPlaceLabel();
                }});

                scotlandSubplotMap.on('click', function() {{
                    if (suppressNextInsetBackgroundClick) {{
                        suppressNextInsetBackgroundClick = false;
                        return;
                    }}
                    clearInsetSelectionRing();
                    hideInsetSelectedPlaceLabel();
                }});
            }}

            scotlandMapDiv.on('plotly_click', function(eventData) {{
                if (!eventData || !eventData.points || !eventData.points.length) return;
                const point = eventData.points[0];
                if (!point.customdata || !point.customdata.length) return;
                if (point.curveNumber < 2) return;

                suppressNextInsetBackgroundClick = true;

                const overlayItem = Array.isArray(overlayControlsAll)
                    ? overlayControlsAll.find((item) => Number(item.inset_trace_index) === Number(point.curveNumber))
                    : null;
                const traditionKey = overlayItem ? String(overlayItem.tradition_key) : null;
                const placeName = point.customdata[1];

                Plotly.restyle(
                    scotlandMapDiv,
                    {{
                        lat: [[point.lat], [point.lat]],
                        lon: [[point.lon], [point.lon]]
                    }},
                    [0, 1]
                );
                showInsetSelectedPlaceLabel(placeName, point.lat, point.lon);

                if (getCurrentMainMapIdentity() === 'scotland' && traditionKey) {{
                    activateTradition(traditionKey, {{ source: 'map' }});
                }}
            }});

            scotlandMapDiv.on('plotly_hover', function(eventData) {{
                if (!eventData || !eventData.points || !eventData.points.length) return;
                const point = eventData.points[0];
                if (!point.customdata || point.curveNumber < 2) return;
                const placeName = point.customdata[1];
                showInsetHoverPlaceLabel(placeName, point.lat, point.lon);
            }});

            scotlandMapDiv.on('plotly_unhover', function() {{
                clearInsetHoverPlaceLabel();
            }});

            scotlandMapDiv.on('plotly_relayout', function() {{
                positionInsetSelectedPlaceLabel();
            }});
        }});

        capeBretonSubplotMap =
            capeBretonMapDiv?._fullLayout?.map?._subplot?.map ||
            capeBretonMapDiv?._fullLayout?.mapbox?._subplot?.map ||
            null;

        window.addEventListener('resize', function() {{
            refitMapsAfterResize();
        }});
    
        capeBretonMapDiv.on('plotly_click', function(eventData) {{
            if (!eventData || !eventData.points || !eventData.points.length) {{
                return;
            }}

            const point = eventData.points[0];
            if (!point.customdata || !point.customdata.length) {{
                return;
            }}

            const placeKey = point.customdata[0];
            activatePlace(placeKey, {{ source: 'map' }});
        }});

        capeBretonMapDiv.on('plotly_hover', function(eventData) {{
            if (!eventData || !eventData.points || !eventData.points.length) {{
                return;
            }}

            const point = eventData.points[0];
            if (!point.customdata || !point.customdata.length) {{
                return;
            }}

            const placeKey = point.customdata[0];
            const place = placesLookup[String(placeKey)];
            if (!place) {{
                return;
            }}

            showCapeBretonHoverPlaceLabel(place, point.lat, point.lon);
        }});

        capeBretonMapDiv.on('plotly_unhover', function() {{
            clearCapeBretonHoverPlaceLabel();
        }});

        capeBretonMapDiv.on('plotly_relayout', function() {{
            positionSelectedPlaceLabel();
        }});

        if (capeBretonSubplotMap && typeof capeBretonSubplotMap.on === 'function') {{
            capeBretonSubplotMap.on('move', function() {{
                positionSelectedPlaceLabel();
            }});
        
            capeBretonSubplotMap.on('zoom', function() {{
                positionSelectedPlaceLabel();
            }});
        
            capeBretonSubplotMap.on('resize', function() {{
                positionSelectedPlaceLabel();
            }});
        }}
    }});

    resetBtn.addEventListener('click', function() {{
        resetMainMapAndPanels();
    }});

    showAllCbBtn.addEventListener('click', function() {{
        showAllTraditionsInCapeBreton();
    }});

    clearAllTraditionsBtn.addEventListener('click', function() {{
        if (!currentOverlayTraditionKeys.length) return;
        setAllVisibleInCurrentOverlayPane(false);
        updateOverlayListActionButton();
    }});
    
    restoreAllTraditionsBtn.addEventListener('click', function() {{
        if (!currentOverlayTraditionKeys.length) return;
        setAllVisibleInCurrentOverlayPane(true);
        updateOverlayListActionButton();
    }});

    modeLocationBtn.addEventListener('click', function() {{
        setSidePanelMode('location');
    }});

    modeAllPeopleBtn.addEventListener('click', function() {{
        setSidePanelMode('all');
    }});

    modeTraditionsBtn.addEventListener('click', function() {{
        setSidePanelMode('traditions');
    }});

    if (peopleDetailLessBtn) {{
        peopleDetailLessBtn.addEventListener('click', function() {{
            decreasePeopleDetail();
        }});
    }}

    if (peopleDetailMoreBtn) {{
        peopleDetailMoreBtn.addEventListener('click', function() {{
            increasePeopleDetail();
        }});
    }}

    document.addEventListener('click', function(event) {{
        const clickedPersonCard = event.target.closest('details.person-card');
        if (clickedPersonCard) return;
    
        const clickedMapMarker = event.target.closest('#map, #cb-main-selected-place-label, #cb-inset-selected-place-label');
        if (clickedMapMarker) return;

        const clickedPanelControl = event.target.closest('#places-index-list, #traditions-index-list, #all-people-list, .index-controls-row, .filters-controls');
        if (clickedPanelControl) return;
    
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
    cape_breton_inset_fig = make_cape_breton_inset_figure(cape_breton_places_df, tradition_specs)
    inset_fig = make_inset_figure(tradition_specs)

    render_html(
        main_fig,
        cape_breton_inset_fig,
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
