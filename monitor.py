import os
import requests
import json
from datetime import datetime, timezone


# minutes offline before a sensor counts as stale
STALE_AFTER_MINUTES = 15

# LimaCharlie's own helper sensors start with this, so it is skipped
IGNORE_PREFIX = "ext-"

# the file where the last run is saved
STATE_FILE = "last_run.json"

# reads the Org ID and API key from the terminal
OID = os.environ["LC_OID"]
KEY = os.environ["LC_API_KEY"]


# send the key to LimaCharlie and get back a temporary pass (JWT)
def get_pass():
    reply = requests.post("https://jwt.limacharlie.io", data={"oid": OID, "secret": KEY})
    return reply.json()["jwt"]


# use the pass to ask LimaCharlie for the list of sensors
def get_sensors(jwt):
    url = "https://api.limacharlie.io/v1/sensors/" + OID
    headers = {"Authorization": "Bearer " + jwt}
    reply = requests.get(url, headers=headers)
    return reply.json()["sensors"]


# how many minutes ago a sensor was last online
def minutes_since(timestamp):
    seen = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - seen).total_seconds() / 60


# get the JWT using the OID and API key, then get the sensors using the JWT
jwt = get_pass()
sensors = get_sensors(jwt)

# problems found this run, and every sensor seen this run
problems = []
current = {}

# go through the sensors one at a time
for s in sensors:
    name = s["hostname"]
    if name.startswith(IGNORE_PREFIX):
        continue  # skip LimaCharlie's helpers

    # write this sensor down so the next run can compare
    current[s["sid"]] = {"name": name, "online": s["is_online"]}

    minutes = minutes_since(s["alive"])
    if not s["is_online"] and minutes > STALE_AFTER_MINUTES:
        problems.append(f"{name} is stale, last seen {minutes:.1f} minutes ago")
    if s["is_isolated"]:
        problems.append(f"{name} is isolated from the network")

# load the last run if there is one
if os.path.exists(STATE_FILE):
    with open(STATE_FILE) as f:
        last = json.load(f)
else:
    last = {}

# anything in the last run that is gone now is missing
for sid in last:
    if sid not in current:
        problems.append(f"{last[sid]['name']} is missing, it was in the last run")

# show the problems
print(f"Problems found: {len(problems)}")
for p in problems:
    print(" ", p)

# save this run for next time
with open(STATE_FILE, "w") as f:
    json.dump(current, f)
