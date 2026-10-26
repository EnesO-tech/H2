# H₂VOLT – Electric & Hydrogen Aircraft Range Studio

Interactive conceptual-design tool for battery-electric, hydrogen fuel-cell and hybrid aircraft. The physics engine is written in Python (`python/h2volt`) and runs directly in the browser via Pyodide.

**Features:** mission simulation (taxi, take-off, climb, cruise, descent, reserve), PEM fuel-cell polarization model, battery equivalent circuit, LH2/CGH2 tanks, maximum range, sizing for a target range with mass snowball, payload–range, trade studies, architecture comparison at equal take-off mass, animated 3D flight with energy flow, built-in validation suite.

## Run

Any static web server, e.g. GitHub Pages, or locally:

```bash
python -m http.server 8000
```

## Python

```bash
cd python
python -m h2volt presets
python -m h2volt run commuter19_fc
python -m h2volt size trainer_battery 80
python -m h2volt validate
python -m pytest -q
```
