# Usage Guide: `oj_download_submissions.py`

This guide explains how to run the Playwright script to download submission statuses from HKUST-GZ OJ contest submissions.

## What it does

- Logs in with your OJ account.
- Enters contest password for a password-protected contest.
- Opens the submissions page (for a problem like `Q01`).
- Switches to `All` submissions (not just `Mine`).
- Scrapes all pages.
- Writes CSV output.

## Prerequisites

1. Python 3.10+.
2. Playwright for Python installed.
3. Chromium browser installed for Playwright.

Example setup:

```bash
python3 -m pip install --user playwright
python3 -m playwright install chromium
```

## Basic command

```bash
python3 oj_download_submissions.py \
  --username YOUR_USERNAME \
  --password YOUR_PASSWORD \
  --contest-password YOUR_CONTEST_PASSWORD \
  --contest-url https://onlinejudge.hkust-gz.edu.cn/contest/31 \
  --submissions-url "https://onlinejudge.hkust-gz.edu.cn/contest/31/submissions?problemID=Q01" \
  --output submissions_q01_all.csv \
  --headless
```

## Filter by year (optional)

If you only want one year (for example 2026):

```bash
python3 oj_download_submissions.py \
  --username YOUR_USERNAME \
  --password YOUR_PASSWORD \
  --contest-password YOUR_CONTEST_PASSWORD \
  --submissions-url "https://onlinejudge.hkust-gz.edu.cn/contest/31/submissions?problemID=Q01" \
  --year 2026 \
  --output submissions_2026.csv \
  --headless
```

If `--year` is omitted, all years are exported.

## Using environment variables (optional)

You can avoid putting credentials directly in the command:

```bash
export OJ_USERNAME="YOUR_USERNAME"
export OJ_PASSWORD="YOUR_PASSWORD"
export OJ_CONTEST_PASSWORD="YOUR_CONTEST_PASSWORD"
```

Then run:

```bash
python3 oj_download_submissions.py \
  --submissions-url "https://onlinejudge.hkust-gz.edu.cn/contest/31/submissions?problemID=Q01" \
  --output submissions_q01_all.csv \
  --headless
```

## Useful options

- `--contest-url`: Contest page URL (default contest 31).
- `--submissions-url`: Submissions page URL.
- `--year`: Integer year filter (omit for all years).
- `--output`: Output CSV file.
- `--cookies`: Path to save Playwright storage state (`cookies.json` by default).
- `--debug-dir`: Save HTML/screenshots for debugging.
- `--timeout-ms`: Timeout per wait step.
- `--headless`: Run browser headlessly.
- `--reuse-cookies`: Start with existing storage-state cookies.
- `--use-proxy-env`: Use `HTTP_PROXY`/`HTTPS_PROXY` from environment.

## Troubleshooting

- `Contest password rejected by server`: verify contest password is current and valid.
- Empty CSV with only header:
  - Check that login succeeded.
  - Check contest password unlock succeeded.
  - Try increasing timeout: `--timeout-ms 20000`.
  - Enable debug dumps: `--debug-dir debug_html`.
- `ERR_CONNECTION_CLOSED`:
  - This can be caused by proxy env vars.
  - By default the script clears proxy env vars.
  - Use `--use-proxy-env` only if your proxy is required and working.

## Output format

CSV columns:

- `When`
- `ID`
- `Status`
- `Problem`
- `Time`
- `Memory`
- `Language`
- `Author`

