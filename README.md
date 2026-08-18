# Garmin Connect Tools

A Python script for managing Garmin Connect activities and integrating with Wahoo fitness data. This tool provides utilities for activity synchronization and management across both platforms.

## Installation

1. Install [Python](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Download dependencies using `uv sync`
3. Activate the venv: `source ./venv/bin/activate` (or `source ./venv/bin/activate.fish` for the fish shell)
4. Create a new `.env` file based on `.env.sample`; a [Wahoo API key](https://developers.wahooligan.com/) is required
5. Start using `garminconnect-tools <mode>`

## Usage

```
Usage: garminconnect-tools <mode>

valid modes:
  elevationCorrection
  getWahooBearer
  getWahooActivities
  getGarminActivities
  wahooImport
  deleteWahooWorkouts
  authenticateGarmin
  fitDate
```

## Features

- Disable elevation correction for all Garmin activities that have it enabled (i.e., use device data instead of Garmin-provided elevation data) (`elevationCorrection`)
- Import activities from Wahoo to Garmin Connect that don't already exist; this uses the exact (down to the second) start date of the activity to avoid duplicates (`wahooImport`)
- Delete specific workouts from your Wahoo account by ID (e.g., broken activities that don't have linked .fit files) (`deleteWahooWorkouts`)
- Obtain and display a Wahoo API bearer token for manual authentication during debugging (`getWahooBearer`)
- Fetch and display all activities from your Wahoo account as JSON (`getWahooActivities`)
- Fetch and display all activities from your Garmin Connect account as JSON (`getGarminActivities`)
- Authenticate with Garmin Connect and save tokens for future use (`authenticateGarmin`)
- Print the start date and time of a given fit file (`fitDate <filename>`)
