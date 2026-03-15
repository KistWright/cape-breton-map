# Architecture
## One-line summary

This project is a Python build script that compiles CSV data and SVG assets into
one standalone HTML application.

## Build-time vs run-time

### Build-time (Python)

Python is responsible for:

- reading the CSVs
- cleaning and normalising the source data
- building lookup tables
- building Plotly figure specs
- embedding assets and data into the final page
- writing the HTML file

### Run-time (browser)

The browser is responsible for:

- rendering the Plotly maps
- handling clicks and tab changes
- swapping main and inset maps
- updating lists and person cards
- turning tradition overlays on and off
- opening and closing the map-controls popup

There is no server-side application logic after build.

## Current input/output model

```text
places.csv
people.csv
communities.csv
traditions.csv
CBscot.svg
SCOTcb.svg
map_controls.svg
    -> generate_map.py
    -> cape_breton_people_map.html
```

## Main architectural pieces

### 1. Source tables

The data model is split across four CSVs:

- `places.csv` supplies geographic master records
- `people.csv` supplies person records
- `communities.csv` links Cape Breton places to traditions
- `traditions.csv` links traditions back to Cape Breton places

### 2. Python cleaning layer

The `clean_*` functions normalise the inputs so the rest of the build can rely
on stable field names and types.

This is the layer that handles things like:

- empty / NaN values
- numeric coercion
- the current `Latitiude` spelling in `places.csv`
- bilingual place-name splitting
- date-field fallback handling

### 3. Python lookup layer

The build then creates the structures the browser will actually use, including:

- place lookup data
- people grouped by place
- flattened all-people index
- per-place tradition lists
- overlay definitions for map traces and checkbox controls

### 4. Figure-building layer

The script currently creates three figure specs:

- Cape Breton main map
- Cape Breton inset map
- Scotland map

The separate Cape Breton inset map is deliberate. It avoids relying on browser
rescaling when Cape Breton is moved into the inset slot.

### 5. HTML application shell

`render_html()` writes the actual browser app. It includes:

- HTML markup
- inline CSS
- inline JavaScript
- embedded Plotly library
- embedded JSON exported from Python

This function is the practical centre of the UI.

## Browser-side state model

The generated page maintains its own in-browser state, including:

- active side tab
- active map-view mode
- selected Cape Breton place
- selected tradition
- visible tradition overlays
- selected person
- current figure in each map slot

This state is not persisted anywhere else.

## Coupling points to be aware of

These are the most tightly coupled parts of the current architecture:

### Python -> JavaScript key names

If a field name or lookup key changes in Python, the JS inside `render_html()`
may also need updating.

### Trace ordering

The browser logic assumes a known trace structure in the prebuilt Plotly figure
specs. Reordering traces in Python can break runtime behaviour.

### HTML ids / classes

The JavaScript refers directly to generated DOM ids and classes. Changing markup
inside `render_html()` often requires matching JS changes.

### Separate Cape Breton inset figure

Current map-swap behaviour depends on the dedicated inset figure. Removing or
simplifying that figure will affect sizing and highlight behaviour.

## Practical maintenance rule

For most changes, ask first which layer the change belongs to:

- source data structure
- cleaning / derivation
- map specification
- UI markup / CSS / JS

That usually tells you exactly where to edit.
