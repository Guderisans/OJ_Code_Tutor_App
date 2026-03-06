#!/usr/bin/env python3
"""
Download submission statuses from HKUST-GZ Online Judge contest submissions page.

This script uses Playwright to log in, handle contest password, navigate to
the submissions page, scrape the table, filter by year, and write a CSV.

"""

from __future__ import annotations

import argparse
import csv
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


LOGIN_BUTTON_RE = re.compile(r"^(login|sign in|log in|登录|登\s*录)$", re.I)
NEXT_BUTTON_RE = re.compile(r"^(next|下一页|下页|>+)$", re.I)
SUBMIT_TIME_HINT_RE = re.compile(r"when|submit|提交时间|提交|time", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download OJ submission statuses.")
    parser.add_argument("--username", default=os.getenv("wenye"))
    parser.add_argument("--password", default=os.getenv("wenye1234"))
    parser.add_argument("--contest-url", default="https://onlinejudge.hkust-gz.edu.cn/contest/65")
    parser.add_argument("--contest-password", default=os.getenv("ufug1601"))
    parser.add_argument("--submissions-url", default="https://onlinejudge.hkust-gz.edu.cn/contest/65/submissions")
    parser.add_argument("--year", type=int, default=None, help="Filter by submit year (e.g. 2026). Omit for all years.")
    parser.add_argument("--output", default="submissions_2026.csv")
    parser.add_argument("--cookies", default="cookies.json")
    parser.add_argument("--debug-dir", default="")
    parser.add_argument("--reuse-cookies", action="store_true", default=False)
    parser.add_argument("--headless", action="store_true", default=False)
    parser.add_argument("--timeout-ms", type=int, default=8000)
    parser.add_argument("--use-proxy-env", action="store_true", default=False)
    args = parser.parse_args()
    if not args.username or not args.password:
        raise SystemExit("Missing --username/--password or OJ_USERNAME/OJ_PASSWORD env vars")
    if not args.contest_password:
        raise SystemExit("Missing --contest-password or OJ_CONTEST_PASSWORD env var")
    return args


def dump_state(page, outdir: str, label: str) -> None:
    if not outdir:
        return
    os.makedirs(outdir, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", label).strip("_")
    html_path = os.path.join(outdir, f"{safe}.html")
    png_path = os.path.join(outdir, f"{safe}.png")
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
    except Exception:
        pass
    try:
        page.screenshot(path=png_path, full_page=True)
    except Exception:
        pass


def _try_fill_first_in(scope, selectors: List[str], value: str) -> bool:
    for sel in selectors:
        loc = scope.locator(sel)
        if loc.count() > 0:
            try:
                loc.first.fill(value)
                return True
            except Exception:
                continue
    return False


def is_logged_in(page) -> bool:
    # Heuristic: login/register buttons not present.
    return page.locator("button", has_text=re.compile(r"Login|Register|登录|注册")).count() == 0


def open_login_modal(page, timeout_ms: int) -> None:
    # If login inputs are already visible, do not toggle modal state.
    if page.locator("input[placeholder='Username']:visible").count() > 0 and page.locator(
        "input[placeholder='Password']:visible"
    ).count() > 0:
        return

    # Click the top-right Login button to open the modal.
    try:
        page.locator(".btn-menu button").filter(has_text=re.compile(r"^Login$|^登录$", re.I)).first.click(
            timeout=1500, force=True
        )
    except Exception:
        # Fallback: use JS click to bypass pointer interception.
        try:
            page.evaluate(
                """
                () => {
                  const btns = Array.from(document.querySelectorAll('button'));
                  const target = btns.find(b => /^(login|sign in|log in|登录|登\\s*录)$/i.test(b.innerText.trim()));
                  if (target) target.click();
                }
                """
            )
        except Exception:
            pass
    page.wait_for_selector("input[placeholder='Password']", timeout=timeout_ms)


def maybe_login(page, username: str, password: str, timeout_ms: int) -> None:
    if is_logged_in(page):
        return

    # Fallback: open login modal on current page.
    open_login_modal(page, timeout_ms)
    user_input = page.locator("input[placeholder='Username']:visible")
    pw_input = page.locator("input[placeholder='Password']:visible")
    if user_input.count() == 0 or pw_input.count() == 0:
        return

    modal = page.locator(".ivu-modal:visible").first
    if modal.count() == 0:
        modal = page

    _try_fill_first_in(modal, ["input[placeholder='Username']", "input[name='username']", "input[name='email']"], username)
    _try_fill_first_in(modal, ["input[placeholder='Password']", "input[type='password']", "input[name='password']"], password)

    # Most reliable on this site: submit by pressing Enter in password box.
    submitted = False
    pw_visible = modal.locator("input[placeholder='Password']:visible")
    if pw_visible.count() > 0:
        try:
            pw_visible.first.press("Enter", timeout=1000)
            submitted = True
        except Exception:
            submitted = False

    if not submitted:
        for name in ["Login", "Sign in", "Log in", "登录", "登 录", "登錄", "Submit"]:
            try:
                modal.get_by_role("button", name=name).first.click(timeout=1000, force=True)
                submitted = True
                break
            except Exception:
                continue
    try:
        page.wait_for_function(
            "() => !Array.from(document.querySelectorAll('button')).some(b => /^(login|登录)$/i.test((b.innerText||'').trim()))",
            timeout=timeout_ms,
        )
    except PlaywrightTimeout:
        pass


def maybe_enter_contest_password(page, contest_password: str, timeout_ms: int) -> None:
    # If contest is password-protected, there is usually a password input and a button to enter.
    try:
        page.wait_for_selector(
            "input[placeholder*='contest password'], input[placeholder*='Contest Password']",
            timeout=timeout_ms,
        )
    except PlaywrightTimeout:
        return

    pw_inputs = page.locator("input[placeholder*='contest password'], input[placeholder*='Contest Password']")
    if pw_inputs.count() == 0:
        return

    filled = False
    try:
        pw_inputs.first.fill(contest_password)
        filled = True
    except Exception:
        pass

    if not filled:
        return

    # Prefer the button in the contest-password block to avoid clicking unrelated controls.
    clicked = False
    local_buttons = page.locator(".contest-password button")
    if local_buttons.count() > 0:
        try:
            local_buttons.first.click(timeout=1000, force=True)
            clicked = True
        except Exception:
            clicked = False

    # Fallback: try common button labels.
    for name in ["Enter", "Join", "Access", "Submit", "确认", "进入", "确定"]:
        if clicked:
            break
        try:
            page.get_by_role("button", name=name).first.click(timeout=1000)
            clicked = True
            break
        except Exception:
            continue

    try:
        page.wait_for_function(
            "() => document.querySelectorAll(\"input[placeholder*='contest password'], input[placeholder*='Contest Password']\").length === 0",
            timeout=timeout_ms,
        )
    except PlaywrightTimeout:
        try:
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except PlaywrightTimeout:
            pass

    # Fail fast only when the gate is still present and a visible error is shown.
    visible_error = page.locator(".ivu-notice-notice:visible", has_text="Wrong password or password expired")
    if pw_inputs.count() > 0 and visible_error.count() > 0:
        raise SystemExit("Contest password rejected by server: wrong password or expired.")


def parse_datetime(text: str) -> Optional[datetime]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None

    # Common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S %z",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    # Try to normalize by stripping timezone label
    text = re.sub(r"\s*\([^\)]*\)$", "", text)
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def extract_table(page) -> Tuple[List[str], List[Dict[str, str]]]:
    table = page.locator(".ivu-table-wrapper").filter(has=page.locator("th:has-text('When')")).first
    if table.count() == 0:
        table = page.locator(".ivu-table-wrapper").first

    headers = [h.strip() for h in table.locator(".ivu-table-header thead tr th").all_text_contents()]
    rows = []
    row_locs = table.locator(".ivu-table-body tbody.ivu-table-tbody tr")
    for i in range(row_locs.count()):
        cells = [c.strip() for c in row_locs.nth(i).locator("td").all_text_contents()]
        row = {headers[j] if j < len(headers) else f"col_{j+1}": cells[j] for j in range(len(cells))}

        # Attach submission link if present
        link = None
        link_loc = row_locs.nth(i).locator("a[href*='submission']")
        if link_loc.count() > 0:
            try:
                link = link_loc.first.get_attribute("href")
            except Exception:
                link = None
        if link:
            row["submission_url"] = link

        rows.append(row)

    return headers, rows


def find_submit_time_field(headers: List[str]) -> Optional[str]:
    for h in headers:
        if SUBMIT_TIME_HINT_RE.search(h):
            return h
    return None


def has_next_page(page) -> Optional[Tuple[str, int]]:
    # Try to find a next page button/link that is enabled.
    candidates = page.locator("a, button")
    for i in range(candidates.count()):
        label = candidates.nth(i).inner_text().strip()
        if not label:
            continue
        if NEXT_BUTTON_RE.match(label):
            # Check disabled state
            aria_disabled = candidates.nth(i).get_attribute("aria-disabled")
            class_attr = candidates.nth(i).get_attribute("class") or ""
            if aria_disabled == "true" or "disabled" in class_attr:
                return None
            return (label, i)
    return None


def enable_all_filter(page, timeout_ms: int) -> None:
    switch = page.locator(".ivu-switch").first
    if switch.count() == 0:
        return
    hidden = switch.locator("input[type='hidden']").first
    current = None
    if hidden.count() > 0:
        try:
            current = (hidden.get_attribute("value") or "").lower()
        except Exception:
            current = None
    # On this OJ: value=true shows "Mine" (only my submissions), value=false shows "All".
    if current == "true":
        try:
            switch.click(timeout=1500, force=True)
        except Exception:
            pass
    try:
        page.get_by_role("button", name="Refresh").first.click(timeout=1500, force=True)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeout:
        pass


def current_page_num(page) -> Optional[int]:
    active = page.locator(".ivu-page-item-active a")
    if active.count() == 0:
        return None
    text = active.first.inner_text().strip()
    try:
        return int(text)
    except Exception:
        return None


def wait_submissions_table(page, timeout_ms: int) -> None:
    try:
        page.wait_for_function(
            """
            () => {
              const spinner = document.querySelector('.ivu-spin-fix');
              if (spinner) return false;
              const rows = document.querySelectorAll('table tbody tr').length;
              const noData = Array.from(document.querySelectorAll('.ivu-table-tip span'))
                .some(el => (el.textContent || '').trim() === 'No Data');
              return rows > 0 || noData;
            }
            """,
            timeout=timeout_ms,
        )
    except PlaywrightTimeout:
        pass


def scrape_all_pages(page, timeout_ms: int, target_year: Optional[int] = None) -> Tuple[List[str], List[Dict[str, str]]]:
    all_rows: List[Dict[str, str]] = []
    headers: List[str] = []
    seen_pages = set()

    while True:
        wait_submissions_table(page, timeout_ms)
        key = current_page_num(page)
        if key in seen_pages:
            break
        seen_pages.add(key)

        headers, rows = extract_table(page)
        all_rows.extend(rows)

        # Optimization for year filtering: submissions are ordered newest -> oldest.
        # Once we see a row older than target_year on the current page, later pages
        # will only be older, so we can stop paginating.
        if target_year is not None:
            submit_field = find_submit_time_field(headers)
            if submit_field:
                has_older = False
                for row in rows:
                    dt = parse_datetime(row.get(submit_field, ""))
                    if dt and dt.year < target_year:
                        has_older = True
                        break
                if has_older:
                    break

        next_link = page.locator(".ivu-page-next:not(.ivu-page-disabled) a")
        if next_link.count() == 0:
            break

        prev_page = current_page_num(page)
        try:
            next_link.first.click(timeout=1500, force=True)
        except Exception:
            try:
                page.evaluate(
                    """
                    () => {
                      const el = document.querySelector('.ivu-page-next:not(.ivu-page-disabled) a');
                      if (el) el.click();
                    }
                    """
                )
            except Exception:
                break
        try:
            page.wait_for_function(
                "(p) => { const el = document.querySelector('.ivu-page-item-active a'); return el && el.textContent && el.textContent.trim() !== String(p); }",
                arg=prev_page if prev_page is not None else "",
                timeout=timeout_ms,
            )
        except PlaywrightTimeout:
            pass

    return headers, all_rows


def main() -> None:
    args = parse_args()
    if not args.use_proxy_env:
        for key in ["HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"]:
            os.environ.pop(key, None)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context()
        if args.reuse_cookies and os.path.exists(args.cookies):
            try:
                context = browser.new_context(storage_state=args.cookies)
            except Exception:
                context = browser.new_context()
        page = context.new_page()

        # Login first on submissions page (modal is reliably available there).
        page.goto(args.submissions_url, wait_until="domcontentloaded")
        dump_state(page, args.debug_dir, "01_submissions_page_initial")
        maybe_login(page, args.username, args.password, args.timeout_ms)
        dump_state(page, args.debug_dir, "02_after_login_attempt")

        # Contest access is password-gated, so unlock contest after login.
        page.goto(args.contest_url, wait_until="domcontentloaded")
        maybe_enter_contest_password(page, args.contest_password, args.timeout_ms)
        dump_state(page, args.debug_dir, "03_after_contest_password")

        # Return to submissions and force all-results mode for the problem.
        page.goto(args.submissions_url, wait_until="domcontentloaded")
        enable_all_filter(page, args.timeout_ms)
        dump_state(page, args.debug_dir, "04_submissions_page_initial")
        headers, rows = scrape_all_pages(page, args.timeout_ms, target_year=args.year)

        submit_field = find_submit_time_field(headers)
        if not submit_field:
            raise SystemExit("Could not find a submit time column in the submissions table.")

        filtered: List[Dict[str, str]] = []
        for row in rows:
            if args.year is None:
                filtered.append(row)
                continue
            submit_time = row.get(submit_field, "")
            dt = parse_datetime(submit_time)
            if dt and dt.year == args.year:
                filtered.append(row)

        # Ensure headers include any extra fields we added (e.g. submission_url)
        extra_fields = sorted({k for r in filtered for k in r.keys()} - set(headers))
        output_headers = headers + extra_fields

        # ======================== 关键修改开始 ========================
        # 1. 定义CSV存储文件夹名称
        csv_folder = "Submissions CSVs"
        # 2. 自动创建文件夹（不存在则创建，存在则不报错）
        os.makedirs(csv_folder, exist_ok=True)
        # 3. 拼接CSV文件的完整路径（文件夹 + 文件名）
        output_path = os.path.join(csv_folder, args.output)
        # ======================== 关键修改结束 ========================

        # 写入CSV文件（使用拼接后的完整路径）
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=output_headers)
            writer.writeheader()
            for row in filtered:
                writer.writerow(row)

        context.storage_state(path=args.cookies)
        browser.close()

    # 打印信息更新：显示实际的存储路径
    print(f"Saved {len(filtered)} rows to {output_path}. Cookies saved to {args.cookies}.")


if __name__ == "__main__":
    main()