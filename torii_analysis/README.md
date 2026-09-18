# Torii SaaS Analysis

Pulls data from the [Torii API](https://developers.toriihq.com) and produces
a spend / license-utilization / shadow-IT report as a self-contained HTML file.

## Setup

```bash
pip install -r requirements.txt
export TORII_API_KEY=<your key>   # Torii dashboard -> Settings -> API
```

`TORII_API_URL` can be set to override the default `https://api.toriihq.com`.

### Network access

This calls `api.toriihq.com` directly. If you're running this from a
sandboxed environment (e.g. Claude Code on the web) with restricted egress,
allow that domain in the environment's network settings first — see
[Configure cloud environments](https://code.claude.com/docs/en/cloud-environments#network-access).
Set `TORII_API_KEY` there too (as an environment variable on the environment,
not committed to the repo) so it isn't typed into chat or version control.

## Usage

```bash
python main.py all       # fetch from the API, then build report.html
python main.py fetch     # just cache raw data under data/raw/
python main.py report    # rebuild report.html from cached data
```

Open `report.html` in a browser.

## What it covers

- **Spend**: total annual SaaS spend, breakdown by app and category
- **License utilization**: active vs. total seats per app, unused seats,
  estimated wasted spend per app
- **Shadow IT / inventory**: full discovered app catalog, apps flagged as
  unmanaged/not-yet-reviewed, breakdown by category

## Notes on field mapping

Torii's exact field names for spend/license data can vary by plan. `fetch.py`
discovers available fields via each resource's `/fields` endpoint and selects
ones matching spend/license/usage keywords; `analyze.py`'s `_first()` helper
then picks whichever of several likely key names is present. If your account
uses different field names than the defaults expect, adjust the keyword
lists in `fetch.py` (`SPEND_KEYWORDS`, `LICENSE_KEYWORDS`, ...) or inspect
`data/raw/apps.json` after a fetch to see the raw shape.
