# Netlify Auto Deploy

This project deploys an anonymized dashboard package, never the local patient
data under `dashboard_ui/data/`.

## How It Works

1. GitHub Actions runs on every push to `main`.
2. `dashboard_ui/scripts/build_netlify_preview.py` reads the committed
   anonymized fixture at `dashboard_ui/demo_data/data_bundle.js`.
3. The script creates `netlify_publish/` and writes `privacy_audit.json`.
4. Deployment continues only when the privacy audit status is `pass`.
5. Netlify CLI deploys `netlify_publish/` to the configured production site.

## Required GitHub Secrets

Set these repository secrets in GitHub before the workflow can deploy:

- `NETLIFY_AUTH_TOKEN`: a Netlify personal access token with deploy access.
- `NETLIFY_SITE_ID`: the Netlify site id, currently
  `7fa5d566-bcb5-4788-8579-913d8e63a35e`.

## Production Gate

Production deploys should only happen when all of the following are true:

- The build uses `dashboard_ui/demo_data/data_bundle.js`, not
  `dashboard_ui/data/data_bundle.js`.
- `privacy_audit.json` reports `status: pass`.
- The publish directory is `netlify_publish/`.
- No real patient names, registration numbers, local paths, Excel filenames, or
  signature metadata are present in the publish directory.
