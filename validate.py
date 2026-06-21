import os
import sqlite3
import sys
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from alert import send_alert

RELEASES_DB = "releases.db"
LOGS_DB = "logs.db"

# Content columns that must be non-null and non-empty per table
CONTENT_COLUMNS = {
    "releases": ["title", "summary", "analogy", "analogy_plain"],
    "blog_posts": ["title", "summary", "analogy", "analogy_plain", "link"],
    "reddit_sentiment": ["summary", "sources_json", "raw_titles_json"],
}

SUMMARY_UNAVAILABLE = "Summary unavailable"


def _already_logged(log_cur, table_name, row_id, error_type):
    log_cur.execute(
        "SELECT 1 FROM errors WHERE table_name=? AND row_id=? AND error_type=? AND fixed=0",
        (table_name, str(row_id), error_type),
    )
    return log_cur.fetchone() is not None


def _log_issue(log_cur, table_name, row_id, error_type, details):
    if _already_logged(log_cur, table_name, row_id, error_type):
        return False
    log_cur.execute(
        "INSERT INTO errors (table_name, row_id, error_type, details, flagged_date, fixed) "
        "VALUES (?, ?, ?, ?, ?, 0)",
        (table_name, str(row_id), error_type, details, date.today().isoformat()),
    )
    return True


def check_empty_fields(rel_con, log_cur):
    issues = 0
    for table, columns in CONTENT_COLUMNS.items():
        cur = rel_con.cursor()
        for col in columns:
            cur.execute(f"SELECT id FROM {table} WHERE {col} IS NULL OR TRIM({col})=''")
            for (row_id,) in cur.fetchall():
                if _log_issue(log_cur, table, row_id, "empty_field",
                              f"Column '{col}' is null or empty"):
                    issues += 1
    return issues


def check_summary_unavailable(rel_con, log_cur):
    issues = 0
    for table, columns in CONTENT_COLUMNS.items():
        cur = rel_con.cursor()
        for col in columns:
            cur.execute(
                f"SELECT id FROM {table} WHERE {col} LIKE ?",
                (f"%{SUMMARY_UNAVAILABLE}%",),
            )
            for (row_id,) in cur.fetchall():
                if _log_issue(log_cur, table, row_id, "summary_unavailable",
                              f"Column '{col}' contains literal '{SUMMARY_UNAVAILABLE}'"):
                    issues += 1
    return issues


def check_dead_urls(rel_con, log_cur):
    issues = 0
    cur = rel_con.cursor()
    cur.execute("SELECT id, link FROM blog_posts WHERE link IS NOT NULL AND TRIM(link) != ''")
    rows = cur.fetchall()
    for row_id, url in rows:
        try:
            req = Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")
            with urlopen(req, timeout=10):
                pass
        except HTTPError as e:
            if e.code >= 400:
                if _log_issue(log_cur, "blog_posts", row_id, "dead_url",
                              f"HEAD {url} returned {e.code}"):
                    issues += 1
        except URLError as e:
            if _log_issue(log_cur, "blog_posts", row_id, "dead_url",
                          f"HEAD {url} failed: {e.reason}"):
                issues += 1
        except TimeoutError:
            if _log_issue(log_cur, "blog_posts", row_id, "dead_url",
                          f"HEAD {url} timed out"):
                issues += 1
    return issues


def recheck_unfixable_urls(rel_con, log_cur):
    recovered = 0
    log_cur.execute(
        "SELECT row_id FROM errors WHERE error_type='dead_url' AND fixed=-1"
    )
    rows = log_cur.fetchall()
    rel_cur = rel_con.cursor()
    for (row_id,) in rows:
        rel_cur.execute(
            "SELECT link FROM blog_posts WHERE id=?", (row_id,)
        )
        row = rel_cur.fetchone()
        if not row or not row[0]:
            continue
        url = row[0]
        try:
            req = Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")
            with urlopen(req, timeout=10):
                pass
            log_cur.execute(
                "UPDATE errors SET fixed=1"
                " WHERE row_id=? AND error_type='dead_url' AND fixed=-1",
                (row_id,),
            )
            recovered += 1
        except (HTTPError, URLError, TimeoutError):
            pass
    return recovered


def main():
    if not os.path.exists(RELEASES_DB):
        print(f"{RELEASES_DB} not found", file=sys.stderr)
        sys.exit(1)

    rel_con = sqlite3.connect(RELEASES_DB)
    log_con = sqlite3.connect(LOGS_DB)
    log_cur = log_con.cursor()

    try:
        empty = check_empty_fields(rel_con, log_cur)
        unavailable = check_summary_unavailable(rel_con, log_cur)
        dead = check_dead_urls(rel_con, log_cur)
        recovered = recheck_unfixable_urls(rel_con, log_cur)
        log_con.commit()
    finally:
        rel_con.close()
        log_con.close()

    total = empty + unavailable + dead
    print(f"Validation complete: {empty} empty fields, {unavailable} 'Summary unavailable', "
          f"{dead} dead URLs — {total} new issue(s) logged, {recovered} previously-dead URL(s) recovered.")

    if total > 0:
        body = (
            f"validate.py found {total} new issue(s) in releases.db:\n\n"
            f"  Empty/null fields:        {empty}\n"
            f"  'Summary unavailable':    {unavailable}\n"
            f"  Dead URLs (blog_posts):   {dead}\n\n"
            f"Check the errors table in logs.db for details."
        )
        send_alert("company-tracker: data quality issues found", body)


if __name__ == "__main__":
    main()
