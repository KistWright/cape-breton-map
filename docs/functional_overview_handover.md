# Functional overview handover

This is the practical walk-through of what the current script does and where a
maintainer should look first.

## 1. Entry point

Start with `main()`.

That function coordinates the whole build:

1. read input files
2. clean the four CSVs
3. derive the working Cape Breton subset
4. calculate people counts and relationships
5. build lookup structures
6. build the Plotly figures
7. call `render_html()`
8. write the finished HTML file

## 2. Cleaning stage

The four `clean_*` functions stabilise the input data before anything else uses
it.

### `clean_places()`

Handles:

- unnamed columns
- required-column checks
- `Latitiude` / `Latitude` normalisation
- numeric coercion for keys and coordinates
- bilingual name splitting

### `clean_people()`

Handles:

- normalising text fields
- validating `Place number`
- creating display and sort names
- preserving date information

### `clean_communities()` and `clean_traditions()`

Handle:

- required-column checks
- integer coercion of key fields
- parsing comma-separated relationship lists

## 3. Lookup-building stage

This is where the script reshapes cleaned tables into structures that are easier
for the browser app to consume.

### `build_people_lookup()`

Creates per-place people lists used when a Cape Breton place is selected.

### `build_all_people_index()`

Creates the People-tab list with names, place labels, IDs, dates, and external
links.

### `build_community_tradition_lookup()`

Creates the per-place tradition lists shown when a place is selected.

### `build_tradition_overlay_specs()`

This is one of the most important functions in the build.

It joins relationship data to place data and produces the overlay definitions
used to:

- colour traditions
- populate checkbox controls
- build Scotland origin markers
- build linked Cape Breton community overlays
- drive hover labels and titles

If tradition overlays are wrong, this function is one of the first places to
check.

## 4. Figure-building stage

The current build uses three figure builders.

### `make_main_figure()`

Builds the main Cape Breton figure and pre-creates overlay traces.

### `make_cape_breton_inset_figure()`

Builds the separate Cape Breton inset figure.

This matters because the inset is not just a resized copy of the main map. It
has its own marker sizing and highlight settings.

### `make_inset_figure()`

Builds the Scotland figure used for traditions.

## 5. HTML app generation

### `render_html()`

This is the main UI-generation function.

It does all of the following in one place:

- serialises the figure specs
- embeds Plotly JS
- embeds Python data as JSON
- writes the page markup
- writes the inline CSS
- writes the inline JavaScript

For practical maintenance, most visible UI changes end up here.

## 6. What the JavaScript currently does

The embedded JS inside `render_html()` currently handles things like:

- tab switching
- list rendering
- place selection
- person-card expansion and selection
- map-view swapping
- tradition overlay visibility
- inset/traditions panel updates
- reset behaviour
- popup open/close behaviour
- resize and label-position updates

## 7. Most common edit types and where they belong

### “I need to change a label, button, layout, or interaction.”

Go to `render_html()`.

### “I need to change marker sizes, colours, centres, or zooms.”

Go to the constants near the top of the script, then check the figure builders.

### “I need to change which people or traditions appear for a place.”

Go to the cleaning functions and lookup builders.

### “I need to change what appears when tradition overlays are toggled.”

Go to `build_tradition_overlay_specs()` and the figure builders.

## 8. Known fragile areas

The current script is strongest as a single-maintainer build file, but these are
the places where edits are easiest to break:

- JSON key names shared between Python and JS
- trace ordering assumptions in the figure specs
- DOM ids and class names referenced by JS
- long inline template sections inside `render_html()`
- source CSV header changes

## 9. Recommended change workflow

1. make the smallest possible edit
2. rebuild the HTML
3. test both map views
4. test all three tabs
5. test one place, one person, one tradition overlay
6. test Reset Map and popup open/close
7. only then move on to the next change

That workflow is slower but much safer with this style of single-file generator.
