# Garmin Connect Tools

A Python script for managing Garmin Connect activities and integrating with Wahoo fitness data. This tool provides utilities for authentication, data synchronization, and activity management across both platforms.

## Installation

1. Install Python and venv
2. Create a new venv: `python3 -m venv venv`
3. Activate the venv: `source ./venv/bin/activate` (or `source ./venv/bin/activate.fish` for fish shell)
4. Install all dependencies: `pip install -r requirements.txt`
5. Create a new `.env` file based on `.env.sample`; a [Wahoo API key](https://developers.wahooligan.com/) is required 

## Usage

```bash
python main.py <mode>
```

## Modes

Modes for regular users:

- `elevationCorrection`: Disable elevation correction for all Garmin activities that have it enabled (i.e., use device data instead of Garmin-provided elevation data)
- `wahooImport`: Import activities from Wahoo to Garmin Connect that don't already exist; this uses the exact (down to the second) start date of the activity
- `deleteWahooWorkouts`: Delete specific workouts from your Wahoo account by ID (e.g., broken activities that don't have linked .fit files)

Modes for advanced users:

- `getWahooBearer`: Obtain and display a Wahoo API bearer token for manual (e.g. `curl`) authentication (only useful for debugging)
- `getWahooActivities`: Fetch and display all activities from your Wahoo account (only useful for debugging)
- `getGarminActivities`: Fetch and display all activities from your Garmin Connect account (only useful for debugging)
- `authenticateGarmin`: Authenticate with Garmin Connect and save tokens for future use (only useful for debugging)
