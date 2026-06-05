# Incubator Tracker — Google Sheets online version

This is a Streamlit version of the Incubator Tracker that stores culture records in Google Sheets instead of a local JSON file.

## Files

- `incubator_tracker_gsheets.py` — Streamlit app
- `requirements.txt` — dependencies for Streamlit Community Cloud
- `.streamlit/config.toml` — Streamlit config

## Google setup

1. Create a Google Sheet, for example `Incubator Tracker Data`.
2. Add a worksheet/tab named `cultures`. The app can create it if the service account has permission, but creating it manually is fine.
3. Create a Google Cloud project.
4. Enable the Google Sheets API.
5. Create a service account and generate a JSON key.
6. Copy the service account email address from the JSON key. It looks like:

   `something@something.iam.gserviceaccount.com`

7. Share your Google Sheet with that service account email and give it Editor access.

## Streamlit secrets

In Streamlit Community Cloud, open your app settings and add secrets like this. Replace all values with the values from your service account JSON.

```toml
sheet_id = "PASTE_THE_GOOGLE_SHEET_ID_HERE"
worksheet_name = "cultures"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

The `sheet_id` is the long ID in the Google Sheet URL:

`https://docs.google.com/spreadsheets/d/SHEET_ID/edit`

Do **not** commit secrets or service account JSON files to GitHub.

## Deploy to Streamlit Community Cloud

1. Create a GitHub repo.
2. Upload these files.
3. In Streamlit Community Cloud, create a new app from the repo.
4. Main file path: `incubator_tracker_gsheets.py`.
5. Add the secrets above in the app settings.
6. Deploy.

## Migrate old JSON data

The app sidebar has a migration tool. Upload your old `incubator_tracker_data.json`, then click **Import JSON into Google Sheet**.

## Obsidian iframe

After deployment, embed the app in Obsidian:

```html
<iframe
  src="https://YOUR_APP_NAME.streamlit.app"
  style="width:90vw; height:88vh; border:0; margin-left:calc(-45vw + 50%);"
></iframe>
```
