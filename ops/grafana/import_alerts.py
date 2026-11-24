"""Import ops/grafana/alerts.yaml into Grafana through the provisioning API.

alerts.yaml is in Grafana's file-provisioning format; the API needs each rule's folder,
group and error state, which this adds. Replaces the whole group, so rerunning it is safe.

    GRAFANA_URL=... GRAFANA_SA_TOKEN=... uv run --with pyyaml ops/grafana/import_alerts.py

The token's service account needs the Editor role (or folders:read and
alert.provisioning:write on the folder).
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ALERTS = Path(__file__).with_name("alerts.yaml")


def seconds(duration: str) -> int:
    return int(duration[:-1]) * {"s": 1, "m": 60, "h": 3600}[duration[-1]]


def call(method: str, path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        os.environ["GRAFANA_URL"].rstrip("/") + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={
            "Authorization": "Bearer " + os.environ["GRAFANA_SA_TOKEN"],
            "Content-Type": "application/json",
            "X-Disable-Provenance": "true",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"{}")


def main(folder_uid: str) -> None:
    (group,) = yaml.safe_load(ALERTS.read_text())["groups"]
    created = False
    try:
        call("GET", f"/api/folders/{folder_uid}")
    except urllib.error.HTTPError as error:
        # A token that may only create folders gets 403, not 404, for one that is missing.
        if error.code not in (403, 404):
            raise
        try:
            call("POST", "/api/folders", {"uid": folder_uid, "title": folder_uid})
            created = True
        except urllib.error.HTTPError as exists:
            if exists.code != 409:
                raise
    rules = [
        {
            **rule,
            "orgID": group["orgId"],
            "folderUID": folder_uid,
            "ruleGroup": group["name"],
            "execErrState": rule.get("execErrState", "Error"),
            "data": [
                dict(d, model=dict(d["model"], refId=d["refId"])) for d in rule["data"]
            ],
        }
        for rule in group["rules"]
    ]
    body = {
        "title": group["name"],
        "interval": seconds(group["interval"]),
        "rules": rules,
    }
    path = f"/api/v1/provisioning/folder/{folder_uid}/rule-groups/{group['name']}"
    # Grafana grants the creator its rights on a new folder a few seconds after creating it.
    attempts = 12 if created else 1
    for attempt in range(attempts):
        try:
            call("PUT", path, body)
            break
        except urllib.error.HTTPError as error:
            if error.code != 403 or attempt == attempts - 1:
                raise
            time.sleep(5)
    print(
        f"imported {len(rules)} rules into folder {folder_uid}, group {group['name']}"
    )


if __name__ == "__main__":
    main(
        sys.argv[1]
        if len(sys.argv) > 1
        else yaml.safe_load(ALERTS.read_text())["groups"][0]["folder"]
    )
