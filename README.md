# Travel with Finn

The Finndex map: https://travelwithfinn.uk

## Editing scores and reasons

Friends with a login edit at **https://travelwithfinn.uk/admin/** (works on phones).
Saves show up on the map straight away. Every save keeps a backup in
`/var/lib/finndex/backups/` on the server (last 200).

Manage logins from this folder:

```sh
./deploy/editors.sh add sam       # you type Sam's password twice
./deploy/editors.sh remove sam
./deploy/editors.sh list
```

## Deploying code changes

```sh
./deploy/deploy.sh
```

This never touches the live data or the logins.

## Layout

- `site/` – public map (`index.html`) and editor (`admin/`)
- `server/finndex_api.py` – save API (stdlib Python, behind nginx basic auth)
- `deploy/` – nginx config, systemd unit, deploy and login scripts
- `tools/build_data.py` – one-off import from the original spreadsheet. The live data
  on the server is now the source of truth; re-importing would overwrite friends' edits.

The spreadsheet and `data.json` are gitignored: this repo is public.
