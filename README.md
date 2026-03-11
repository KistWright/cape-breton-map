# Cainnt is Ceathramhan  
### Map of People and Traditions

Interactive map visualising informants and associated Scottish traditions connected to Cape Breton communities.

The map displays:

- locations of informants in Cape Breton
- Scottish traditions associated with those communities
- links between people, places, and traditions
- an inset map showing Scottish origins of traditions

The project generates a **stand-alone HTML web application** using a Python script and several structured CSV datasets.

---

# Live Map

The current version of the map can be viewed here:

**[Open the Map](./index.html)**

This HTML file is self-contained and can be hosted on GitHub Pages or opened locally.

---

# Repository Structure
.
├─ index.html
│
├─ scripts/
│ └─ generate_map.py
│
├─ data/
│ ├─ places.csv
│ ├─ people.csv
│ ├─ communities.csv
│ └─ traditions.csv
│
├─ docs/
│ ├─ architecture.md
│ └─ data_structure.md
│
└─ README.md

### index.html
The generated interactive map application.

### scripts/generate_map.py
Python script that reads the CSV files and produces the HTML map.

### data/
Contains the source datasets used to build the map.

### docs/
Technical documentation for developers and collaborators.

---

# How the Map is Generated

The workflow is:

CSV datasets
↓
Python processing script
↓
Plotly map figures
↓
HTML + CSS + JavaScript generation
↓
Standalone interactive web map


The script embeds:

- Plotly JavaScript
- the map data
- interface logic

directly into the generated HTML file.

---

# Regenerating the Map

If the data changes, regenerate the HTML map using:

python scripts/generate_map.py


This will create a new `index.html` file.

Commit the updated HTML file to publish the changes.

---

# Data Sources

The map is built from four datasets:

| File | Description |
|-----|-------------|
| places.csv | Master list of geographic locations |
| people.csv | Informants linked to places |
| communities.csv | Links between Cape Breton communities and traditions |
| traditions.csv | Scottish traditions linked to Cape Breton communities |

Detailed descriptions are available in:

docs/data_structure.md


---

# Future Development

Possible future improvements include:

- separating HTML, CSS, and JavaScript into independent files
- replacing CSV inputs with a database backend
- exposing data through a REST API
- dynamic loading of records via JSON

See:


docs/architecture.md


---

# Credits

Map built using:

- Python
- Plotly
- MapLibre / OpenStreetMap tiles
