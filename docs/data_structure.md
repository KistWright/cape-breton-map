# Data structure handover

This note describes the source files the current build expects and the main
structures derived from them.

## Core rule

`places.csv` is the master geographic table.

Everything else links back to it by numeric place key.

## 1. `places.csv`

### Current role

Supplies the place key, bilingual place label, and coordinates for both:

- Cape Breton communities
- Scottish origin / tradition places

### Current columns in the working file

| Column | Notes |
|---|---|
| `Place Number` | primary geographic key |
| `Community of Origin (Canada)` | bilingual label, usually `Gaelic | English` |
| `Latitiude` | current source spelling; script normalises it |
| `Longitude` | longitude |

### Derived fields created by `clean_places()`

| Field | Meaning |
|---|---|
| `place_key` | cleaned integer key |
| `place_name` | original bilingual name |
| `place_name_gaelic` | Gaelic side |
| `place_name_english` | English side |
| `latitude` | cleaned numeric latitude |
| `longitude` | cleaned numeric longitude |

## 2. `people.csv`

### Current role

Supplies person records linked to Cape Breton places.

This file drives:

- place-specific people lists
- the People tab
- person page links
- recordings links

### Current columns present in the working file

| Column | Notes |
|---|---|
| `Person number` | internal numeric row/id field |
| `Informant ID` | external person identifier used in URLs |
| `Informant Last Name` | English surname |
| `Informant Maiden Name` | optional |
| `Informant First Name` | English given name |
| `Nickname/Familiar Name` | optional |
| `Cinneadh` | Gaelic surname |
| `Cinneadh-breithe` | Gaelic birth surname |
| `Ainm` | Gaelic given name |
| `Sloinneadh` | extended Gaelic naming field |
| `Dates` | display dates |
| `Place number` | foreign key to `places.csv` |
| `Number of Recordings` | count displayed in cards |
| `Unnamed: 13` / `Unnamed: 14` / `Unnamed: 15` | currently present but not structurally central |

### Important derived fields

| Field | Meaning |
|---|---|
| `gaelic_name` | assembled Gaelic display name |
| `english_name` | assembled English display name |
| `display_name` | primary display label |
| `sort_name` | normalised sort value |
| `person_page_url` | live person-page URL |
| `recordings_url` | anchored recordings-section URL |

## 3. `communities.csv`

### Current role

Links Cape Breton communities to one or more Scottish traditions.

### Current columns

| Column | Notes |
|---|---|
| `Community` | Cape Breton place key |
| `Traditions` | comma-separated tradition place keys |

### Derived field

| Field | Meaning |
|---|---|
| `Tradition_keys` | parsed list of integer tradition keys |

## 4. `traditions.csv`

### Current role

Links Scottish tradition places back to Cape Breton communities.

### Current columns

| Column | Notes |
|---|---|
| `Tradition` | Scottish tradition place key |
| `Communities` | comma-separated Cape Breton place keys |

### Derived field

| Field | Meaning |
|---|---|
| `Community_keys` | parsed list of integer Cape Breton keys |

## Relationship model in plain language

```text
people.csv
    -> points to Cape Breton place keys
communities.csv
    -> maps Cape Breton place keys to tradition place keys
traditions.csv
    -> maps tradition place keys back to Cape Breton place keys
places.csv
    -> supplies the names and coordinates for all of those keys
```

## Derived browser-side structures you are most likely to encounter

The script exports several structures into the HTML/JS layer. The most important
ones for maintenance are:

- `placesLookup`
- `peopleByPlace`
- `allPeopleIndex`
- per-place tradition lookup data
- `overlayControlsAll`
- prebuilt Plotly figure specs

## Data assumptions to preserve

- place keys are numeric and stable across files
- `people.csv` place references point only to Cape Breton communities used by the UI
- tradition/community relationship fields can be parsed as comma-separated numeric lists
- bilingual place labels remain splittable on `|` where both languages are present

If any of those assumptions change, the cleaning functions and likely part of the
browser logic will need updating.
