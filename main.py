#!/usr/bin/env python3

from datetime import datetime, timedelta
from garminconnect import Garmin
from getpass import getpass
from pathlib import Path
from typing import Any
import dotenv
import json
import os
import re
import requests
import subprocess
import sys
import tempfile

WAHOO_BASE_URL = "https://api.wahooligan.com"
DEFAULT_GARMIN_TOKENSTORE = "garmin_tokenstore"
DEFAULT_WAHOO_TOKENS_FILE = "wahoo_tokens.json"


def yesno(prompt: str) -> bool:
    user_input = input(f"> {prompt} [y/N] ")
    if user_input.strip().lower() != "y":
        return False
    return True


def load_wahoo_tokens() -> dict[str, str] | None:
    wahoo_tokens_file = os.getenv("WAHOO_TOKENS_FILE", DEFAULT_WAHOO_TOKENS_FILE)
    if not os.path.exists(wahoo_tokens_file):
        return None

    with open(wahoo_tokens_file, "r") as f:
        return json.load(f)


def save_wahoo_tokens(filename: str, tokens: dict[str, str]) -> None:
    with open(filename, "w") as f:
        json.dump(tokens, f, indent=2)


def is_wahoo_token_expired(tokens: dict[str, str]) -> bool:
    if not tokens or "expires_at" not in tokens:
        return True

    expires_at = datetime.fromisoformat(tokens["expires_at"])
    return datetime.now() + timedelta(minutes=5) >= expires_at


def refresh_wahoo_tokens(refresh_token: str) -> dict[str, str]:
    client_id = os.getenv("WAHOO_CLIENT_ID")
    client_secret = os.getenv("WAHOO_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise Exception("Wahoo client ID and client secret are required")

    url = f"{WAHOO_BASE_URL}/oauth/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    response = requests.post(url, data=data)

    if response.status_code != 200:
        raise Exception(f"Failed to refresh token: {response.text} (status {response.status_code})")

    token_data = response.json()
    expires_at = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600 * 2))

    tokens = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_at": expires_at.isoformat(),
    }

    filename = os.getenv("WAHOO_TOKENS_FILE", DEFAULT_WAHOO_TOKENS_FILE)
    save_wahoo_tokens(filename, tokens)
    print(f"Saved refreshed tokens to {filename}")
    return tokens


def get_wahoo_code() -> str:
    client_id = os.getenv("WAHOO_CLIENT_ID")
    redirect_uri = os.getenv("WAHOO_REDIRECT_URI")
    scopes = os.getenv("WAHOO_SCOPES")

    if not client_id or not redirect_uri or not scopes:
        raise Exception("Wahoo client ID, redirect URI, and scopes are required")

    response_type = "code"
    url = f"{WAHOO_BASE_URL}/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scopes}&response_type={response_type}"

    print(f"Opening {url} in browser")
    subprocess.run(["open", url])

    code = input("> Enter code from URL in browser: ").strip()
    return code


def get_wahoo_bearer() -> str:
    tokens = load_wahoo_tokens()

    if tokens and not is_wahoo_token_expired(tokens):
        print("Using existing valid access token")
        return tokens["access_token"]

    if tokens and "refresh_token" in tokens:
        print("Token is expired, refreshing...")
        new_tokens = refresh_wahoo_tokens(tokens["refresh_token"])
        if new_tokens:
            print("Token refreshed successfully")
            return new_tokens["access_token"]
        else:
            print("Token refresh failed, need to re-authorize")

    code = get_wahoo_code()

    client_secret = os.getenv("WAHOO_CLIENT_SECRET")
    redirect_uri = os.getenv("WAHOO_REDIRECT_URI")
    client_id = os.getenv("WAHOO_CLIENT_ID")

    if not client_secret or not redirect_uri or not client_id:
        raise Exception("Wahoo client secret, redirect URI, and client ID are required")

    url = f"{WAHOO_BASE_URL}/oauth/token?client_secret={client_secret}&code={code}&redirect_uri={redirect_uri}&grant_type=authorization_code&client_id={client_id}"

    response = requests.post(url)

    if response.status_code != 200:
        raise Exception(f"Failed to get token: {response.text} (status {response.status_code})")

    token_data = response.json()
    expires_at = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600 * 2))

    tokens = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_at": expires_at.isoformat(),
    }

    filename = os.getenv("WAHOO_TOKENS_FILE", DEFAULT_WAHOO_TOKENS_FILE)
    save_wahoo_tokens(filename, tokens)
    print(f"Saved wahoo tokens to {filename}")
    return tokens["access_token"]


def garmin_elevation_correction(
    garmin: Garmin,
    all_activities: list[dict[str, Any]],
) -> None:
    elevation_corrected = [x for x in all_activities if x["elevationCorrected"] is True]

    if len(elevation_corrected) == 0:
        print("no activities with elevation correction found")
        return

    print(f"found {len(elevation_corrected)} activities with corrected elevation data:")
    for e in elevation_corrected:
        print(f"  {e['activityId']}, {e['activityType']['typeKey']}")

    if not yesno("Disable elevation correction for all these activities?"):
        return

    for act in elevation_corrected:
        id = act["activityId"]
        print(f"Updating elevation correction for activity {id}")

        url = f"/activity-service/activity/toggleElevationCorrection/{act['activityId']}"
        response = garmin.garth.post("connectapi", url, data={"elevationCorrected": "true"})

        if response.status_code < 200 or response.status_code > 299:
            print(f"Failed to update elevation correction for activity {id}: {response.text} (status {response.status_code})")
            break


def authenticate_garmin() -> Garmin:
    garmin_tokenstore = os.getenv("GARMIN_TOKENSTORE", DEFAULT_GARMIN_TOKENSTORE)
    tokenstore_path = Path(garmin_tokenstore).expanduser()

    use_saved_tokens = False

    if tokenstore_path.exists():
        print("Found existing Garmin token directory")
        token_files = list(tokenstore_path.glob("*.json"))
        if token_files:
            print(f"Found {len(token_files)} Garmin token file(s): {', '.join([f.name for f in token_files])}")
            use_saved_tokens = True
        else:
            print("Token directory exists but no token files found")

    if use_saved_tokens:
        try:
            print("Logging in with existing Garmin authentication tokens...")
            garmin = Garmin()
            garmin.login(str(tokenstore_path))
            return garmin
        except Exception as e:
            print(f"Error logging in with existing Garmin authentication tokens: {e}")
            print("Re-authenticating with Garmin credentials...")

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    if not email:
        email = input("> Garmin login email: ").strip()
    if not password:
        password = getpass("> Garmin password: ")

    print("Logging in with Garmin credentials...")
    garmin = Garmin(
        email=email,
        password=password,
        is_cn=False,
        return_on_mfa=True,
    )
    result1, result2 = garmin.login()

    if result1 == "needs_mfa":
        mfa_code = input("> Multi-factor authentication required: ").strip()
        garmin.resume_login(result2, mfa_code)

    garmin.garth.dump(str(tokenstore_path))
    print(f"Garmin authentication tokens saved to: {tokenstore_path}")
    return garmin


def get_all_garmin_activities(garmin: Garmin) -> list[dict[str, Any]]:
    page = 0
    all_activities = []

    while True:
        print(f"Downloading Garmin activities page {page + 1}")
        activities = garmin.get_activities(start=page * 20, limit=20)
        if activities is None:
            raise TypeError("expected activities to be a list of activities, not None")

        all_activities.extend(activities.copy())

        if len(activities) < 20:
            break
        page += 1

    return all_activities


def get_all_wahoo_activities(
    bearer: str,
    ignore_workouts: bool,
) -> list[dict[str, Any]]:
    page = 1
    per_page = 100
    all_activities = []

    while True:
        print(f"Downloading Wahoo activities page {page}")
        url = f"{WAHOO_BASE_URL}/v1/workouts?page={page}&per_page={per_page}"
        response = requests.get(url, headers={"Authorization": f"Bearer {bearer}"})

        if ignore_workouts:
            new = [a for a in response.json()["workouts"] if a["workout_summary"] is not None]
            all_activities.extend(new)
        else:
            all_activities.extend(response.json()["workouts"])

        if len(response.json()["workouts"]) < per_page:
            break
        page += 1

    return all_activities


def gmt_to_rfc3339(gmt_time: str) -> str:
    isoformat = datetime.strptime(gmt_time, "%Y-%m-%d %H:%M:%S").isoformat()
    return f"{isoformat}.000Z"


def wahoo_import(garmin: Garmin, bearer: str) -> None:
    garmin_activities = get_all_garmin_activities(garmin)
    wahoo_activities = get_all_wahoo_activities(bearer, True)

    id_time_garmin = {}
    for activity in garmin_activities:
        id_time_garmin[activity["activityId"]] = gmt_to_rfc3339(activity["startTimeGMT"])

    id_time_wahoo = {}
    for activity in wahoo_activities:
        id_time_wahoo[activity["id"]] = activity["starts"]

    import_ids = [k for k, v in id_time_wahoo.items() if v not in id_time_garmin.values()]
    import_activities = [activity for activity in wahoo_activities if activity["id"] in import_ids]

    if len(import_activities) == 0:
        print("No activities to import, all Wahoo activities are already in Garmin")
        return

    print(f"Importing {len(import_activities)} activities to Garmin")
    for activity in import_activities:
        print(f"  {activity['name']} ({activity['id']}, started at {activity['starts']})")

    skip = input("> IDs to skip (comma separated): ").strip()
    if skip == "":
        skip = []
    else:
        skip = [int(id.strip()) for id in skip.split(",")]
        import_activities = [activity for activity in import_activities if activity["id"] not in skip]

    temp_dir = tempfile.mkdtemp()
    print(f"Downloading .fit files to {temp_dir}")

    fit_files = []

    for activity in import_activities:
        if activity["workout_summary"] is None or activity["workout_summary"]["file"] is None:
            print(f"  {activity['name']} ({activity['id']}, started at {activity['starts']}): No workout summary or file! Can't upload to Garmin")
            continue

        fit_url = activity["workout_summary"]["file"]["url"]
        fit_filename = re.sub(r".*\/", "", fit_url)

        print(f"Downloading {fit_url}")
        fit_data = requests.get(fit_url).content

        path = os.path.join(temp_dir, fit_filename)
        fit_files.append(path)

        with open(path, "wb") as f:
            f.write(fit_data)

    for fit_file in fit_files:
        print(f"Uploading {fit_file} to Garmin")
        try:
            response = garmin.upload_activity(fit_file)
            print(f"Uploaded FIT file: {response.status_code}")
        except Exception as e:
            print(f"Failed to upload {fit_file} to Garmin: {e}")
            continue
        print(f"Uploaded {fit_file} to Garmin")

    return


def delete_wahoo_workouts(bearer: str) -> None:
    while True:
        id = input("> ID to delete: ").strip()
        if not id:
            break

        url = f"{WAHOO_BASE_URL}/v1/workouts/{id}"
        response = requests.delete(url, headers={"Authorization": f"Bearer {bearer}"})
        if response.status_code < 200 or response.status_code > 299:
            print(f"Failed to delete activity {id}: {response.text} (status {response.status_code})")
            continue
        print(f"Deleted activity {id}")


def main() -> None:
    dotenv.load_dotenv()

    valid_modes = [
        "elevationCorrection",
        "getWahooBearer",
        "getWahooActivities",
        "getGarminActivities",
        "wahooImport",
        "deleteWahooWorkouts",
        "authenticateGarmin",
    ]

    if len(sys.argv) < 2:
        print("Usage: garminconnect-tools <mode>\n\nvalid modes:")
        for mode in valid_modes:
            print(f"  {mode}")
        return

    mode = sys.argv[1]

    if mode not in valid_modes:
        print("Invalid mode.")
        return

    args = sys.argv[2:]

    if mode == "elevationCorrection":
        garmin = authenticate_garmin()
        all_activities = get_all_garmin_activities(garmin)
        garmin_elevation_correction(garmin, all_activities)
    if mode == "getWahooBearer":
        bearer = get_wahoo_bearer()
        print(bearer)
    if mode == "getWahooActivities":
        bearer = get_wahoo_bearer()
        if "--ignore-workouts" in args:
            ignore_workouts = True
        else:
            print("tip: use `--ignore-workouts` to ignore planned workouts")
            ignore_workouts = False
        all_activities = get_all_wahoo_activities(bearer, ignore_workouts)
        print(json.dumps(all_activities))
    if mode == "getGarminActivities":
        garmin = authenticate_garmin()
        all_activities = get_all_garmin_activities(garmin)
        print(json.dumps(all_activities))
    if mode == "wahooImport":
        garmin = authenticate_garmin()
        bearer = get_wahoo_bearer()
        wahoo_import(garmin, bearer)
    if mode == "deleteWahooWorkouts":
        bearer = get_wahoo_bearer()
        delete_wahoo_workouts(bearer)
    if mode == "authenticateGarmin":
        garmin = authenticate_garmin()
        print("Garmin authenticated successfully")


if __name__ == "__main__":
    main()
