# Functional Overview of the Map Generation Script

This document provides a functional overview of the Python script that generates the interactive map HTML file. It explains how the script processes data, builds map figures, and produces the final HTML, JavaScript, and CSS used by the application.

## Overall Purpose

The Python script performs four main tasks:

1. Loads and cleans data from four CSV files.
2. Builds structured lookup objects for places, people, and traditions.
3. Creates two Plotly map figures in Python.
4. Writes a complete standalone HTML file containing:
   - CSS styling
   - Page structure (HTML)
   - Embedded Plotly map data
   - Embedded JavaScript for interactivity

The script therefore does more than feed an HTML template. It assembles the entire webpage as a large string and writes it to disk.

## 1. Constants and Configuration

Defined near the top of the script.

### Input and Output Files

- `PLACES_CSV`
- `PEOPLE_CSV`
- `COMMUNITIES_CSV`
- `TRADITIONS_CSV`
- `OUTPUT_HTML`

### Map Configuration

- `MAP_CENTER`
- `MAP_ZOOM`
- `SCOTLAND_CENTER`
- `SCOTLAND_ZOOM`

### Visual Styling

- `ACCENT`
- `TITLE_COLOUR`
- `BODY_TEXT`
- `PANEL_BG`
- `BANNER_BG`
- `TRADITION_COLOURS`

These constants control:

- which files are loaded
- where the output HTML is written
- map positioning
- colour schemes used in both Plotly and CSS

They affect both:

- Plotly figures created in Python
- CSS and JavaScript embedded in the HTML output

## 2. Utility Functions

These small helper functions normalise and parse incoming data.

### `cleaned_text(value)`

Normalises text values by:

- converting `None` / `NaN` to empty strings
- stripping whitespace
- removing literal `"nan"`

Used whenever text is read from CSV files.

### `first_present_value(row, column_names)`

Returns the first non-empty value from a list of possible column names.

Used primarily for flexible date-column detection.

### `parse_number_list(value)`

Converts comma-separated numeric strings into integer lists.

Example:

```text
"12, 14, 18"
```

becomes:

```text
[12, 14, 18]
```

Used for community–tradition relationships.

### `split_bilingual_name(value)`

Splits bilingual fields of the form:

```text
Gaelic Name | English Name
```

into:

```text
(gaelic_name, english_name)
```

### `format_bilingual_plain(gaelic, english)`

Builds a plain bilingual display string.

Used for hover labels and simple display contexts.

## 3. CSV Cleaning Functions

These functions convert raw CSV data into consistent pandas DataFrames.

### `clean_places(df)`

Performs the following steps:

- removes unnamed columns
- standardises column names
- validates required fields
- converts coordinates and keys to numeric types
- removes incomplete rows
- splits bilingual place names into:
  - `place_name_gaelic`
  - `place_name_english`

This cleaned dataset becomes the foundation for all map points and place labels.

### `clean_people(df)`

Processes the people dataset by:

- validating the `"Place number"` column
- converting place references to integers
- normalising text fields
- constructing:
  - `gaelic_name`
  - `english_name`
  - `display_name`
  - `sort_name`

This dataset powers both:

- **People by selected location**
- **List All People**

### `clean_communities(df)`

Processes the communities dataset by:

- validating column structure
- converting `Community` to integer
- parsing tradition lists into:
  - `Tradition_keys`

### `clean_traditions(df)`

Processes the traditions dataset by:

- validating column structure
- converting `Tradition` to integer
- parsing linked communities into:
  - `Community_keys`

## 4. Lookup-Building Functions

These functions convert cleaned data into Python structures that are later embedded into JavaScript.

### `build_people_lookup(people_df)`

Creates a dictionary:

```text
place_key → list of people
```

Used to populate the **Location Details** panel when a map marker is clicked.

### `build_all_people_index(people_df, places_df)`

Creates a flattened list of all people including:

- names
- place of origin
- coordinates
- sorting keys
- alphabetical index letter

This powers the **List All People** interface.

### `build_community_tradition_lookup(...)`

Builds a lookup mapping Cape Breton communities to associated traditions.

Used to populate:

- the **Associated Traditions** panel
- overlay controls

### `build_tradition_overlay_specs(...)`

This function links traditions to map overlays.

It generates structures containing:

- tradition colour
- Scotland tradition point
- linked Cape Breton communities
- hover labels
- trace ordering metadata

These structures are used to create:

- additional Plotly traces
- overlay UI controls

## 5. Plotly Figure Generation

Two Plotly maps are generated before HTML creation.

### `make_main_figure(...)`

Creates the Cape Breton map.

It adds:

- base markers for all Cape Breton places
- two empty highlight-ring traces
- one hidden trace for each tradition overlay

The JavaScript layer later toggles these traces on and off.

### `make_inset_figure(...)`

Creates the Scotland inset map.

It adds:

- two highlight traces
- one hidden Scotland marker for each tradition

Again:

- Python builds the layers
- JavaScript controls their visibility

## 6. HTML Generation (`render_html()`)

This function builds the entire webpage.

### A. Convert Plotly Figures

```python
main_fig_dict = main_fig.to_dict()
inset_fig_dict = inset_fig.to_dict()
```

These dictionaries are embedded into JavaScript.

### B. Embed Plotly JavaScript

```python
plotly_js = get_plotlyjs()
```

This embeds the Plotly library directly into the HTML so the output file is fully self-contained.

### C. Build Browser Lookups

Python prepares browser-side lookup structures such as:

- `places_lookup`
- `overlay_controls_all`

### D. Generate the HTML Document

The page is built as a large Python f-string:

```python
html = f"""
<!DOCTYPE html>
<html>
...
</html>
"""
```

This includes:

#### `<head>`

- metadata
- page title
- embedded Plotly library
- CSS styles

#### Page Structure

- banner
- side panel
- tabbed panels
- map container
- inset map container
- overlay panel
- controls and buttons

#### JavaScript

Includes:

- data injected from Python
- all interaction logic
- Plotly initialisation

### E. Write the HTML File

```python
output_path.write_text(html, encoding="utf-8")
```

This produces the final standalone HTML application.

## 7. What Generates the HTML?

All HTML markup is generated inside the `render_html()` f-string.

Examples include:

```html
<header class="banner">
<aside class="side-panel">
<div id="map">
```

These elements are written directly into the output file.

## 8. What Generates the CSS?

The CSS is embedded in the `<style>` block inside `render_html()`.

Example:

```html
<style>
...
</style>
```

Python constants such as:

- `{ACCENT}`
- `{BODY_TEXT}`
- `{BANNER_BG}`

are interpolated into this block.

There is no external stylesheet.

## 9. What Generates the JavaScript?

The JavaScript is embedded in the `<script>` block.

It contains two components.

### A. Data Exported From Python

Python objects are converted to JavaScript using `json.dumps()`:

```javascript
const mainFigureSpec = ...
const placesLookup = ...
const peopleByPlace = ...
```

This transfers structured data from Python to the browser.

### B. Embedded JavaScript Logic

Functions written directly into the HTML include:

- `renderPlace()`
- `renderAllPeopleList()`
- `selectPersonCard()`
- `showLocationTraditionsSection()`
- `toggleLocationTraditionsSection()`
- `setOverlayPanelVisibility()`
- `setInsetPanelVisibility()`
- `resetMainMapAndPanels()`

Python injects the data, while JavaScript defines the browser behaviour.

## 10. Relationship Between Python and JavaScript

### Python

Responsible for:

- reading CSV files
- cleaning data
- linking datasets
- building map traces
- generating lookup structures
- embedding data into HTML

### JavaScript

Responsible for:

- user interactions
- marker selection
- panel updates
- overlay toggling
- map redrawing
- UI state changes

## 11. Plotly Usage

Plotly is used in two stages.

### In Python

Plotly figures are constructed:

- `main_fig`
- `inset_fig`

These contain all traces and layout information.

### In the Browser

The figures are recreated using:

```javascript
Plotly.newPlot(...)
```

The browser simply renders the specification built by Python.

## 12. The `main()` Function

`main()` orchestrates the entire process.

It:

- resolves file paths
- loads CSV files
- cleans datasets
- identifies Cape Breton places
- calculates people counts
- builds lookup structures
- creates Plotly figures
- calls `render_html()`
- writes the HTML file

## 13. Functional Responsibilities

### Data Cleaning

- `clean_places`
- `clean_people`
- `clean_communities`
- `clean_traditions`

### Data Structures

- `build_people_lookup`
- `build_all_people_index`
- `build_community_tradition_lookup`
- `build_tradition_overlay_specs`

### Map Construction

- `make_main_figure`
- `make_inset_figure`

### Page Generation

- `render_html`

### Execution Pipeline

- `main`

## 14. Key Answer: What Generates the HTML and JavaScript?

### HTML

Generated inside the large f-string in:

```python
render_html(...)
```

### JavaScript

Generated inside the same function, especially:

```html
<script>...</script>
```

and the data export lines using:

```python
json.dumps(...)
```

## 15. Mental Model of the Script

The script acts as a build system for a small web application.

```text
CSV datasets
     ↓
Python data processing
     ↓
Plotly map construction
     ↓
HTML + CSS + JavaScript generation
     ↓
Standalone interactive webpage
```

The final HTML file is therefore a fully self-contained web app produced by the Python script.
