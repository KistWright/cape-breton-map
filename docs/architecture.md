# System Architecture

This document describes how the map application is generated and how the codebase is structured.

---

# Overview

The project is implemented as a **static web application generator**.

A Python script processes several CSV datasets and produces a fully self-contained HTML application containing:

- HTML structure
- CSS styling
- Plotly map figures
- JavaScript interaction logic
- embedded dataset lookups

The resulting HTML file functions as a small standalone web application.

---

# Processing Pipeline


CSV datasets
↓
Data cleaning (Python)
↓
Lookup construction
↓
Plotly figure generation
↓
HTML template assembly
↓
Standalone HTML application


---

# Python Script Responsibilities

The Python script performs several roles:

## Data Processing

- reads CSV files
- cleans inconsistent values
- parses relationships between places, people, and traditions

## Data Structuring

Builds lookup dictionaries used by the frontend interface.

Examples:

- people by place
- traditions by community
- alphabetical index of people

## Map Construction

Creates two Plotly figures:

- main Cape Breton map
- Scotland inset map

These figures include all traces needed for overlays and highlighting.

## HTML Generation

The script writes the final HTML file using a large template string.

This template contains:

- CSS styling
- page layout
- embedded JavaScript
- embedded data structures

---

# Frontend Behaviour

Once the HTML file loads in the browser, JavaScript manages:

- marker selection
- side panel population
- people list expansion
- tradition overlays
- inset map highlighting
- UI state changes

Plotly handles map rendering.

---

# Future Architecture

If the project evolves beyond a static HTML generator, the system could be refactored into:


database
↓
API service
↓
JavaScript frontend
↓
dynamic map application


Possible technologies:

- FastAPI / Flask backend
- PostgreSQL database
- JSON API endpoints
- modular JavaScript frontend

This would allow:

- live data updates
- search and filtering
- user-generated content
- dynamic loading of records
