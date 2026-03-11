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
                    "id": cleaned_text(row.get("Informant ID", "")),
                    "yob_yod": yob_yod,
                    "sloinneadh": cleaned_text(row.get("Sloinneadh", "")),
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
        gaelic_name = cleaned_text(row.get("gaelic_name", ""))
        english_name = cleaned_text(row.get("english_name", ""))
        display_name = cleaned_text(row.get("display_name", ""))
        initial = (english_last[:1] or display_name[:1] or "#").upper()
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
        cb_places_hover = "<br><br>".join(
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

    .side-panel-mode-toggle {{
        display: flex;
        gap: 6px;
        margin-bottom: 0;
        flex-wrap: nowrap;
        align-items: flex-end;
        position: relative;
        z-index: 3;
    }}
    
    details.person-card.selected > summary,
    details.all-people-card.selected > summary {{
        background: #1F5F99;
        color: #ffffff;
    }}
    
    details.person-card.selected .english-highlight-person,
    details.all-people-card.selected .english-highlight-person {{
        color: #ffffff;
    }}
    
    details.person-card.selected > summary::after,
    details.all-people-card.selected > summary::after {{
        color: #ffffff;
    }}
    
    details.person-card.selected .separator-accent,
    details.all-people-card.selected .separator-accent {{
        color: #ffffff;
    }}

    .mode-btn {{
        position: relative;
        padding: 10px 16px 9px 16px;
        border: 1px solid rgba(25, 41, 48, 0.15);
        border-bottom: 1px solid rgba(25, 41, 48, 0.12);
        background: #f4f8fb;
        color: {BODY_TEXT};
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        cursor: pointer;
        border-radius: 8px 8px 0 0;
        box-shadow: none;
        margin-bottom: -1px;
    }}
    
    .mode-btn.active {{
        background: #ffffff;
        color: {TITLE_COLOUR};
        border-color: rgba(25, 41, 48, 0.12);
        border-bottom-color: #ffffff;
        box-shadow: none;
        z-index: 4;
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
    }}
    
    .location-lower-panel {{
        flex: 0 0 calc(46px + 8px + 22vh);
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-top: 8px;
        min-height: 0;
    }}
    
    .location-traditions-toggle-wrap {{
        flex: 0 0 46px;
    }}
    
    #location-traditions-toggle-btn {{
        width: 100%;
        height: 46px;
        display: none;
        text-align: center;
    }}
    
    .associated-pane {{
        flex: 0 0 22vh;
        min-height: 0;
        max-height: 22vh;
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
        position: absolute;
        z-index: 1003;
        padding: 8px 12px;
        border: 1px solid rgba(25, 41, 48, 0.15);
        background: rgba(255, 255, 255, 0.98);
        color: {BODY_TEXT};
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        cursor: pointer;
        border-radius: 4px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
    }}

    .overlay-toggle-btn:hover,
    .inset-toggle-btn:hover {{
        border-color: {ACCENT};
        color: {ACCENT};
    }}

    .overlay-toggle-btn {{
        right: 16px;
        bottom: 16px;
    }}

    .inset-toggle-btn {{
        top: 12px;
        right: 64px;
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
        bottom: 56px;
    }}

    .floating-inset {{
        top: 48px;
        right: 16px;
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

    .person-card,
    .people-master-card {{
        background: {CARD_BG};
        border: 1px solid rgba(25, 41, 48, 0.08);
        border-left: 4px solid {ACCENT};
        border-radius: 6px;
        margin-bottom: 10px;
        overflow: hidden;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }}

    details.person-card summary,
    details.people-master-card summary {{
        cursor: pointer;
        padding: 10px 12px;
        list-style: none;
        color: {BODY_TEXT};
        background: #fff;
        font-size: 14px;
        line-height: 19px;
    }}

    details.person-card summary {{
        text-transform: none;
    }}

    details.person-card summary::-webkit-details-marker,
    details.people-master-card summary::-webkit-details-marker {{
        display: none;
    }}

    details.person-card > summary::after,
    details.people-master-card > summary::after {{
        content: '+';
        float: right;
        color: {ACCENT};
        font-size: 0.95rem;
        margin-left: 1rem;
        font-weight: 700;
    }}

    details.person-card[open] > summary::after,
    details.people-master-card[open] > summary::after {{
        content: '–';
    }}
    
    #informants-pane details.location-person-card > summary .person-summary-name,
    #all-people-list details.all-people-card > summary .person-summary-name {{
        font-weight: 700;
    }}
    
    .metadata,
    .people-master-metadata {{
        padding: 10px 12px 12px 12px;
        border-top: 1px solid rgba(25, 41, 48, 0.06);
        background: #f7fbfe;
    }}

    .meta-block {{
        margin-bottom: 8px;
    }}

    .meta-line {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 1rem;
        margin-bottom: 8px;
        flex-wrap: wrap;
    }}

    .meta-line-left,
    .meta-line-right {{
        min-width: 0;
    }}

    .meta-line-right {{
        margin-left: auto;
        text-align: right;
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

    .english-highlight-place {{
        color: {ACCENT};
    }}

    .english-highlight-person {{
        color: {ACCENT};
        font-style: italic;
    }}

    .person-summary-name {{
        display: inline;
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

    #map .mapboxgl-ctrl-bottom-right,
    #map .maplibregl-ctrl-bottom-right,
    #inset-map .mapboxgl-ctrl-bottom-right,
    #inset-map .maplibregl-ctrl-bottom-right {{
        display: none !important;
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

    .meta-line-right {{
        margin-left: 0;
        text-align: left;
    }}

    .selected-place-label {{
        max-width: 280px;
        white-space: normal;
        transform: translate(16px, -100%);
    }}

    :root {{
        --floating-panel-width: min(74vw, 300px);
        --floating-panel-min-width: 0px;
        --floating-panel-height: 42%;
    }}

    .floating-overlays {{
        right: 12px;
        bottom: 52px;
    }}

    .floating-inset {{
        top: 48px;
        right: 12px;
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
            <span class="gaelic-banner">Mapa Dhaoine is Dhualchasan</span>
            <span class="english-highlight-banner">Map of People and Traditions</span>
        </div>
    </header>

    <div class="content">
        <aside class="side-panel">
            <div class="side-panel-mode-toggle">
                <button id="mode-location-btn" class="mode-btn active" type="button">Location details</button>
                <button id="mode-all-people-btn" class="mode-btn" type="button">List All People</button>
            </div>

            <div id="location-panel-view" class="panel-view active">
                <div class="info-header">
                    <p class="intro">Click a map marker to list all linked people for that place.</p>
                </div>
            
                <div id="place-header"></div>
            
                <div id="informants-pane" class="informants-pane">
                    <div class="empty">Select a place on the map to begin.</div>
                </div>
            
                <div class="location-lower-panel">
                    <div class="location-traditions-toggle-wrap">
                        <button id="location-traditions-toggle-btn" class="map-reset-btn" type="button">
                            Show traditions associated with this place
                        </button>
                    </div>
            
                    <div id="associated-pane" class="associated-pane" hidden></div>
                </div>
            </div>

            <div id="all-people-panel-view" class="panel-view">
                <div class="info-header">
                    <p class="intro">Browse all people alphabetically by English surname. Click a person to highlight their place of origin on the main map.</p>
                </div>
                <div class="people-list-controls">
                    <button id="people-toggle-all-btn" class="tiny-btn" type="button">Hide all people</button>
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

            <div id="floating-inset" class="floating-panel floating-inset hidden">
                <div class="floating-panel-header">
                    <div class="section-title">Associated traditions</div>
                </div>
                <div class="floating-panel-body" style="position:relative;">
                    <div id="inset-selected-place-label" class="inset-selected-place-label"></div>
                    <div id="inset-map"></div>
                </div>
            </div>

            <button id="inset-toggle-btn" class="inset-toggle-btn" type="button">Show inset</button>

            <div id="floating-overlays" class="floating-panel floating-overlays hidden">
                <div class="floating-panel-header">
                    <div class="section-title">Associated traditions</div>
                    <p class="intro">Select or deselect traditions to highlight linked Cape Breton communities.</p>
                </div>
                <div class="floating-panel-body">
                    <div class="filters-controls">
                        <button id="show-all-cb-pane-btn" class="tiny-btn" type="button">Show all traditions in Cape Breton</button>
                        <button id="show-all-traditions" class="tiny-btn" type="button">Show all</button>
                        <button id="clear-all-traditions" class="tiny-btn" type="button">Clear all</button>
                    </div>
                    <div id="overlay-list" class="overlay-list">
                        <div class="overlay-empty">Select a Cape Breton place to load associated traditions.</div>
                    </div>
                </div>
            </div>

            <button id="overlay-toggle-btn" class="overlay-toggle-btn" type="button">Show overlays</button>

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
    const locationTraditionsToggleBtn = document.getElementById('location-traditions-toggle-btn');
    const INITIAL_CENTER = {json.dumps(MAP_CENTER)};
    const INITIAL_ZOOM = {MAP_ZOOM};

    function escapeHtml(value) {{
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
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

    function resetInfoPanel() {{
        placeHeader.innerHTML = '';
        informantsPane.innerHTML = '<div class="empty">Select a place on the map to begin.</div>';
        associatedPane.innerHTML = '';
        associatedPane.hidden = true;
        locationTraditionsToggleBtn.style.display = 'none';
        locationTraditionsToggleBtn.textContent = 'Show traditions associated with this place';
        currentLocationPlaceKey = null;
        locationTraditionsVisible = false;
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

    function clearAllTraditionsAndControls() {{
        setAllTraditionsVisibleByKeys([], false);
        renderOverlayControls([]);
        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();
        setOverlayPanelVisibility(false);
        setInsetPanelVisibility(false);
        Plotly.redraw(mapDiv);
        Plotly.redraw(insetMapDiv);
    }}

    function showAllTraditionsInCapeBreton() {{
        resetInfoPanel();
        clearSelectionRing();
        hideSelectedPlaceLabel();
        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();

        const allKeys = overlayControlsAll.map((item) => String(item.tradition_key));
        renderOverlayControls(allKeys);
        setAllTraditionsVisibleByKeys(allKeys, true);

        document.querySelectorAll('.tradition-toggle').forEach((checkbox) => {{
            checkbox.checked = true;
        }});

        setOverlayPanelVisibility(true);
        setInsetPanelVisibility(true);

        Plotly.redraw(mapDiv);
        Plotly.redraw(insetMapDiv);
    }}

    function resetMainMapAndPanels() {{
        resetInfoPanel();
        clearSelectionRing();
        hideSelectedPlaceLabel();
        clearAllTraditionsAndControls();

        Plotly.relayout(mapDiv, {{
            'map.center.lat': INITIAL_CENTER.lat,
            'map.center.lon': INITIAL_CENTER.lon,
            'map.zoom': INITIAL_ZOOM
        }});
    }}

    function renderAssociatedTraditions(traditions) {{
        if (!traditions || !traditions.length) {{
            return '';
        }}

        let html = '<div class="associated-box">';
        html += '<div class="section-title">Associated traditions</div>';
        html += '<ul class="associated-list">';

        for (const item of traditions) {{
            const colour = item.colour || '{ACCENT}';
            const label = formatBilingualHtml(item.gaelic || '', item.english || '');

            html += `<li><span class="associated-bullet" style="background:${{escapeHtml(colour)}};"></span><span>${{label}}</span></li>`;
        }}

        html += '</ul></div>';
        return html;
    }}


    function hideLocationTraditionsSection() {{
        locationTraditionsVisible = false;
        associatedPane.hidden = true;
        associatedPane.innerHTML = '';
        locationTraditionsToggleBtn.style.display = 'block';
        locationTraditionsToggleBtn.textContent = 'Show traditions associated with this place';
        clearAllTraditionsAndControls();
    }}
    
    function showLocationTraditionsSection(placeKey) {{
        const place = placesLookup[String(placeKey)];
        if (!place) return;
    
        associatedPane.innerHTML = renderAssociatedTraditions(place.traditions || []);
        associatedPane.hidden = false;
    
        const associatedKeys = (place.traditions || []).map((item) => String(item.key));
        renderOverlayControls(associatedKeys);
        setAllTraditionsVisibleByKeys(associatedKeys, true);
    
        document.querySelectorAll('.tradition-toggle').forEach((checkbox) => {{
            checkbox.checked = true;
        }});
    
        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();
        setOverlayPanelVisibility(true);
        setInsetPanelVisibility(true);
    
        locationTraditionsVisible = true;
        currentLocationPlaceKey = String(placeKey);
        locationTraditionsToggleBtn.style.display = 'block';
        locationTraditionsToggleBtn.textContent = 'Hide associated traditions';
    
        Plotly.redraw(mapDiv);
        Plotly.redraw(insetMapDiv);
    }}
    
    function toggleLocationTraditionsSection() {{
        if (!currentLocationPlaceKey) return;
    
        if (locationTraditionsVisible) {{
            hideLocationTraditionsSection();
        }} else {{
            showLocationTraditionsSection(currentLocationPlaceKey);
        }}
    }}

    function renderPlace(placeKey) {{
        const place = placesLookup[String(placeKey)];
        const people = (peopleByPlace[String(placeKey)] || []).slice().sort((a, b) =>
            a.sort_name.localeCompare(b.sort_name) || a.name.localeCompare(b.name)
        );
    
        if (!place) {{
            placeHeader.innerHTML = '';
            informantsPane.innerHTML = '<div class="empty">No data found for that place.</div>';
            associatedPane.innerHTML = '';
            associatedPane.hidden = true;
            locationTraditionsToggleBtn.style.display = 'none';
            clearAllTraditionsAndControls();
            return;
        }}
    
        currentLocationPlaceKey = String(placeKey);
        locationTraditionsVisible = false;
    
        let headerHtml = '';
        const placeGaelic = place.place_name_gaelic || '';
        const placeEnglish = place.place_name_english || '';
    
        if (placeGaelic && placeEnglish) {{
            headerHtml += `<div class="place-title"><strong>${{escapeHtml(placeGaelic)}}<span class="separator-accent"> | </span><span class="english-highlight-place">${{escapeHtml(placeEnglish)}}</span></strong></div>`;
        }} else if (placeEnglish) {{
            headerHtml += `<div class="place-title"><strong><span class="english-highlight-place">${{escapeHtml(placeEnglish)}}</span></strong></div>`;
        }} else {{
            headerHtml += `<div class="place-title"><strong>${{escapeHtml(placeGaelic || place.place_name)}}</strong></div>`;
        }}
    
        headerHtml += `<div class="place-meta"><span class="gaelic-dark">Luchd-aithris</span><span class="separator-accent"> | </span><span class="english-accent">Informants</span>: ${{people.length}}</div>`;
        placeHeader.innerHTML = headerHtml;
    
        if (!people.length) {{
            informantsPane.innerHTML = '<div class="empty">No people are linked to this place key.</div>';
        }} else {{
            let peopleHtml = '';
            for (const person of people) {{
                const gaelicName = person.gaelic_name || '';
                const englishName = person.english_name || '';
    
                let summaryName = '';
                if (gaelicName && englishName) {{
                    summaryName = `${{escapeHtml(gaelicName)}}<span class="separator-accent"> / </span><span class="english-highlight-person">${{escapeHtml(englishName)}}</span>`;
                }} else if (englishName) {{
                    summaryName = `<span class="english-highlight-person">${{escapeHtml(englishName)}}</span>`;
                }} else {{
                    summaryName = escapeHtml(gaelicName || person.name);
                }}
    
                peopleHtml += `
                    <details class="person-card location-person-card"
                        data-place-key="${{escapeHtml(String(placeKey))}}"
                        data-lat="${{escapeHtml(String(place.latitude))}}"
                        data-lon="${{escapeHtml(String(place.longitude))}}">
                        <summary><span class="person-summary-name">${{summaryName}}</span></summary>
                        <div class="metadata">
                            <div class="meta-line">
                                <div class="meta-line-left">
                                    <div class="meta-label">ID</div>
                                    <div class="meta-inline-value">${{escapeHtml(person.id || '—')}}</div>
                                </div>
                                <div class="meta-line-right">
                                    <div class="meta-label">Dates</div>
                                    <div class="meta-inline-value">${{escapeHtml(person.yob_yod || '—')}}</div>
                                </div>
                            </div>
                            <div class="meta-block">
                                <div class="meta-label">Sloinneadh</div>
                                <div class="meta-value">${{escapeHtml(person.sloinneadh || '—')}}</div>
                            </div>
                        </div>
                    </details>`;
            }}
            informantsPane.innerHTML = peopleHtml;
        }}
    
        associatedPane.innerHTML = '';
        associatedPane.hidden = true;
        locationTraditionsToggleBtn.style.display = 'block';
        locationTraditionsToggleBtn.textContent = 'Show traditions associated with this place';
    
        clearInsetSelectionRing();
        hideInsetSelectedPlaceLabel();
        clearAllTraditionsAndControls();
    
        wireLocationPersonSelectionBehaviour();
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

    function renderOverlayControls(activeTraditionKeys) {{
        const keySet = new Set((activeTraditionKeys || []).map(String));
        const items = overlayControlsAll.filter((item) => keySet.has(String(item.tradition_key)));

        if (!items.length) {{
            overlayList.innerHTML = '<div class="overlay-empty">Select a Cape Breton place to load associated traditions.</div>';
            return;
        }}

        overlayList.innerHTML = items.map((item) => buildOverlayRowHtml(item, true)).join('');

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
        floatingOverlays.classList.toggle('hidden', !isVisible);
        overlayToggleBtn.textContent = isVisible ? 'Hide overlays' : 'Show overlays';
        overlayToggleBtn.setAttribute('aria-expanded', String(isVisible));
    }}

    function setInsetPanelVisibility(isVisible) {{
        floatingInset.classList.toggle('hidden', !isVisible);
        insetToggleBtn.textContent = isVisible ? 'Hide inset' : 'Show inset';
        insetToggleBtn.setAttribute('aria-expanded', String(isVisible));
    
        if (isVisible) {{
            setTimeout(() => {{
                Plotly.Plots.resize(insetMapDiv);
            }}, 0);
        }}
    }}

    function setSidePanelMode(mode) {{
        const showLocation = mode === 'location';
        locationPanelView.classList.toggle('active', showLocation);
        allPeoplePanelView.classList.toggle('active', !showLocation);
        modeLocationBtn.classList.toggle('active', showLocation);
        modeAllPeopleBtn.classList.toggle('active', !showLocation);
    
        if (showLocation) {{
            clearSelectedPerson();
            }} else {{
                associatedPane.hidden = true;
                associatedPane.innerHTML = '';
                locationTraditionsToggleBtn.textContent = 'Show traditions associated with this place';
                locationTraditionsVisible = false;
                clearAllTraditionsAndControls();
            }}
    }}

    function buildAllPeopleListHtml() {{
        if (!allPeopleIndex.length) {{
            return '<div class="people-empty">No people found.</div>';
        }}
    
        const grouped = {{}};
        for (const person of allPeopleIndex) {{
            const letter = person.letter || '#';
            if (!grouped[letter]) grouped[letter] = [];
            grouped[letter].push(person);
        }}
    
        const letters = Object.keys(grouped).sort();
        let html = '';
    
        for (const letter of letters) {{
            html += `<details class="people-letter-group" open>`;
            html += `<summary>${{escapeHtml(letter)}}</summary>`;
            html += `<div class="people-letter-group-body">`;
    
            for (const person of grouped[letter]) {{
                let summaryName = '';
                if (person.gaelic_name && person.english_name) {{
                    summaryName = `${{escapeHtml(person.gaelic_name)}}<span class="separator-accent"> / </span><span class="english-highlight-person">${{escapeHtml(person.english_name)}}</span>`;
                }} else if (person.english_name) {{
                    summaryName = `<span class="english-highlight-person">${{escapeHtml(person.english_name)}}</span>`;
                }} else {{
                    summaryName = escapeHtml(person.display_name || person.id || 'Unnamed person');
                }}
    
                const placeLabel = formatBilingualHtml(
                    person.place_name_gaelic || '',
                    person.place_name_english || ''
                );
    
                html += `
                    <details class="person-card all-people-card"
                        data-place-key="${{escapeHtml(person.place_key)}}"
                        data-lat="${{escapeHtml(person.latitude)}}"
                        data-lon="${{escapeHtml(person.longitude)}}">
                        <summary><span class="person-summary-name">${{summaryName}}</span></summary>
                        <div class="metadata">
                            <div class="meta-line">
                                <div class="meta-line-left">
                                    <div class="meta-label">ID</div>
                                    <div class="meta-inline-value">${{escapeHtml(person.id || '—')}}</div>
                                </div>
                                <div class="meta-line-right">
                                    <div class="meta-label">Dates</div>
                                    <div class="meta-inline-value">${{escapeHtml(person.yob_yod || '—')}}</div>
                                </div>
                            </div>
                            <div class="meta-block">
                                <div class="meta-label">Sloinneadh</div>
                                <div class="meta-value">${{escapeHtml(person.sloinneadh || '—')}}</div>
                            </div>
                            <div class="meta-block">
                                <div class="meta-label">Place of origin</div>
                                <div class="meta-value">${{placeLabel}}</div>
                            </div>
                        </div>
                    </details>`;
            }}
    
            html += `</div></details>`;
        }}
    
        return html;
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

    function clearSelectedPerson() {{
        document.querySelectorAll('details.person-card.selected, details.all-people-card.selected').forEach((card) => {{
            card.classList.remove('selected');
        }});
    
        selectedPersonCard = null;
        clearSelectionRing();
        hideSelectedPlaceLabel();
    }}
    
    function selectPersonCard(card) {{
        if (!card) return;
    
        document.querySelectorAll('details.person-card.selected, details.all-people-card.selected').forEach((el) => {{
            if (el !== card) el.classList.remove('selected');
        }});
    
        selectedPersonCard = card;
        selectedPersonCard.classList.add('selected');
    
        const placeKey = card.dataset.placeKey;
        const lat = Number(card.dataset.lat);
        const lon = Number(card.dataset.lon);
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
    
    function wirePersonSelectionBehaviour() {{
        document.querySelectorAll('#all-people-list details.all-people-card').forEach((card) => {{
            const summary = card.querySelector(':scope > summary');
            if (!summary) return;
    
            summary.addEventListener('click', function(event) {{
                selectPersonCard(card);
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
            peopleToggleAllBtn.textContent = 'Hide all people';
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
            peopleToggleAllBtn.textContent = 'Hide all people';
        }}
    }}
    
    function collapseAllLetterGroups() {{
        document.querySelectorAll('#all-people-list details.people-letter-group').forEach((el) => {{
            el.open = false;
        }});
        document.querySelectorAll('#all-people-list details.all-people-card').forEach((el) => {{
            el.open = false;
        }});
        visibleRecordsExpanded = false;
        previousVisibleRecordStates = new Map();
        allPeopleShown = false;
        if (peopleToggleAllBtn) {{
            peopleToggleAllBtn.textContent = 'Show all people';
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
    
            const cards = group.querySelectorAll('details.all-people-card');
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
        document.querySelectorAll('#informants-pane details.location-person-card').forEach((card) => {{
            const summary = card.querySelector(':scope > summary');
            if (!summary) return;
    
            summary.addEventListener('click', function() {{
                selectPersonCard(card);
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
    const showAllTraditionsBtn = document.getElementById('show-all-traditions');
    const clearAllTraditionsBtn = document.getElementById('clear-all-traditions');
    const floatingOverlays = document.getElementById('floating-overlays');
    const overlayToggleBtn = document.getElementById('overlay-toggle-btn');
    const floatingInset = document.getElementById('floating-inset');
    const insetToggleBtn = document.getElementById('inset-toggle-btn');
    const placeHeader = document.getElementById('place-header');
    const informantsPane = document.getElementById('informants-pane');
    const associatedPane = document.getElementById('associated-pane');

    const modeLocationBtn = document.getElementById('mode-location-btn');
    const modeAllPeopleBtn = document.getElementById('mode-all-people-btn');
    const locationPanelView = document.getElementById('location-panel-view');
    const allPeoplePanelView = document.getElementById('all-people-panel-view');
    const allPeopleList = document.getElementById('all-people-list');
    const peopleToggleAllBtn = document.getElementById('people-toggle-all-btn');
    const peopleExpandVisibleBtn = document.getElementById('people-expand-visible-btn');

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
    let locationTraditionsVisible = false;

    Plotly.newPlot(
        mapDiv,
        mainFigureSpec.data,
        mainFigureSpec.layout,
        {{
            responsive: true,
            displaylogo: false,
            displayModeBar: true
        }}
    ).then(function() {{
        keepOnlySnapshotButton();

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
            renderOverlayControls([]);
            setOverlayPanelVisibility(false);
            setInsetPanelVisibility(false);
            setSidePanelMode('location');
            
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
            const place = placesLookup[String(placeKey)];
            setSidePanelMode('location');
            renderPlace(placeKey);

            Plotly.restyle(
                mapDiv,
                {{
                    lat: [[point.lat], [point.lat]],
                    lon: [[point.lon], [point.lon]]
                }},
                [1, 2]
            );

            if (place) {{
                showSelectedPlaceLabel(place, point.lat, point.lon);
            }}
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

    showAllTraditionsBtn.addEventListener('click', function() {{
        setAllVisibleInCurrentOverlayPane(true);
    }});

    showAllCbBtn.addEventListener('click', function() {{
        showAllTraditionsInCapeBreton();
    }});

    showAllCbPaneBtn.addEventListener('click', function() {{
        showAllTraditionsInCapeBreton();
    }});

    clearAllTraditionsBtn.addEventListener('click', function() {{
        setAllVisibleInCurrentOverlayPane(false);
    }});

    overlayToggleBtn.addEventListener('click', function() {{
        const willShow = floatingOverlays.classList.contains('hidden');
        setOverlayPanelVisibility(willShow);
    }});

    insetToggleBtn.addEventListener('click', function() {{
        const willShow = floatingInset.classList.contains('hidden');
        setInsetPanelVisibility(willShow);
    }});

    modeLocationBtn.addEventListener('click', function() {{
        setSidePanelMode('location');
    }});

    modeAllPeopleBtn.addEventListener('click', function() {{
        setSidePanelMode('all');
        if (peopleToggleAllBtn) {{
            peopleToggleAllBtn.textContent = allPeopleShown ? 'Hide all people' : 'Show all people';
        }}
    }});

        peopleToggleAllBtn.addEventListener('click', function() {{
        toggleAllLetterGroups();
    }});
    
    peopleExpandVisibleBtn.addEventListener('click', function() {{
        expandVisiblePeopleRecords();
    }});

    document.addEventListener('click', function(event) {{
        const clickedPersonCard = event.target.closest('details.all-people-card, details.person-card');
        if (clickedPersonCard) return;
    
        const clickedMapMarker = event.target.closest('#map, #selected-place-label');
        if (clickedMapMarker) return;
    
        clearSelectedPerson();
    }});

    locationTraditionsToggleBtn.addEventListener('click', function() {{
        toggleLocationTraditionsSection();
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
