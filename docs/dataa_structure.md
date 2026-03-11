# Data Structure

This document describes the CSV datasets used to build the map.

---

# places.csv

Master list of locations used by the map.

| Field | Description |
|------|-------------|
| Place Number | Unique identifier for the place |
| Community of Origin (Canada) | Bilingual place name |
| Latitude | Latitude coordinate |
| Longitude | Longitude coordinate |

Example:


12, Mabou | Mabù, 46.1, -61.4


Place names are split into Gaelic and English components during processing.

---

# people.csv

List of informants associated with places.

| Field | Description |
|------|-------------|
| Informant ID | Unique person identifier |
| Ainm | Gaelic first name |
| Cinneadh | Gaelic surname |
| Informant First Name | English first name |
| Informant Last Name | English surname |
| Place number | Place key linking to places.csv |

These records populate:

- the Location Details panel
- the alphabetical list of people

---

# communities.csv

Links Cape Breton communities to traditions.

| Field | Description |
|------|-------------|
| Community | Cape Breton place key |
| Traditions | Comma-separated list of tradition keys |

Example:


15, 4,6,9


---

# traditions.csv

Links Scottish traditions to Cape Breton communities.

| Field | Description |
|------|-------------|
| Tradition | Scottish place key |
| Communities | List of Cape Breton communities linked to that tradition |

These records control:

- tradition overlays
- inset map points
- associated traditions panel

---

# Relationship Diagram


People
↓
Places
↓
Communities
↓
Traditions


A place may have:

- many people
- multiple traditions
- connections to multiple Scottish regions
