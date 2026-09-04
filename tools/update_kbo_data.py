#!/usr/bin/env python3
"""KBO 퓨처스 순위와 잔여 일정을 data.js로 생성한다."""

from __future__ import annotations

import html
import http.cookiejar
import json
import os
import re
import tempfile
import threading
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE = "https://www.koreabaseball.com"
SCHEDULE_URL = f"{BASE}/Futures/Schedule/GameList.aspx"
RANK_URLS = {
    "north": f"{BASE}/Futures/TeamRank/North.aspx",
    "south": f"{BASE}/Futures/TeamRank/South.aspx",
}
FORM_PREFIX = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$"
TEAM_COLORS = {
    "상무": "#ef3124", "한화": "#f37321", "LG": "#c30452",
    "고양": "#7d1638", "두산": "#131230", "SSG": "#ce0e2d",
    "울산": "#0b4da2", "롯데": "#041e42", "NC": "#315288",
    "KIA": "#ea0029", "KT": "#231f20", "삼성": "#074ca1",
}
KST = timezone(timedelta(hours=9))


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag != "input":
            return
        values = dict(attrs)
        if values.get("type") == "hidden" and values.get("name"):
            self.hidden[values["name"]] = values.get("value", "")


def opener():
    jar = http.cookiejar.CookieJar()
    return build_opener(HTTPCookieProcessor(jar))


def fetch(client, url: str, data: dict[str, str] | None = None) -> str:
    body = urlencode(data).encode() if data else None
    request = Request(url, data=body, headers={
        "User-Agent": "Mozilla/5.0 FuturesNumber/1.0",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    with client.open(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def text_content(fragment: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", fragment, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(html.unescape(value).split())


def parse_standings(page: str) -> list[dict]:
    marker = "순위  | 팀명"
    # 실제 HTML의 첫 번째 순위 테이블에서 tbody만 선택한다.
    tables = re.findall(r"<table[^>]*>(.*?)</table>", page, flags=re.S | re.I)
    table = next((t for t in tables if "최근10경기" in t and "게임차" in t), "")
    teams = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, flags=re.S | re.I):
        cells = [text_content(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.S | re.I)]
        if len(cells) < 9 or not cells[0].isdigit():
            continue
        rank, name, games, wins, losses, draws = cells[:6]
        teams.append({
            "name": name, "g": int(games), "w": int(wins),
            "l": int(losses), "d": int(draws), "remain": 0,
            "recent10": cells[8],
            "color": TEAM_COLORS.get(name, "#777777"),
        })
    if len(teams) != 6:
        raise RuntimeError(f"순위표에서 6개 팀을 찾지 못했습니다: {len(teams)}개")
    return teams


def month_page(client, initial_page: str, year: int, month: int) -> str:
    parser = FormParser()
    parser.feed(initial_page)
    fields = parser.hidden
    fields.update({
        f"{FORM_PREFIX}ddlYear": str(year),
        f"{FORM_PREFIX}ddlMonth": f"{month:02d}",
        f"{FORM_PREFIX}hfSearchTeam": "ALL",
        f"{FORM_PREFIX}hfSearchDate": f"{year}-{month:02d}-01",
        f"{FORM_PREFIX}btnSearch": "",
    })
    return fetch(client, SCHEDULE_URL, fields)


def parse_remaining_games(page: str, year: int, month: int, after: date):
    current_day = None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S | re.I):
        date_match = re.search(r"lblGameDate_[^>]*>(\d{2})\.(\d{2})", row)
        if date_match:
            current_day = int(date_match.group(2))
        if current_day is None:
            continue
        game_date = date(year, month, current_day)
        if game_date < after:
            continue
        play = re.search(r'<td class="play">(.*?)</td>', row, flags=re.S | re.I)
        note = re.search(r'<td class="etc">(.*?)</td>', row, flags=re.S | re.I)
        if not play:
            continue
        note_text = text_content(note.group(1)) if note else ""
        if "취소" in note_text:
            continue
        names = re.findall(r"<span[^>]*>([^<]+)</span>", play.group(1))
        names = [text_content(name) for name in names if text_content(name) != "vs"]
        if len(names) == 2:
            yield game_date, names[0], names[1]


def parse_completed_games(page: str, year: int, month: int, through: date):
    current_day = None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S | re.I):
        date_match = re.search(r"lblGameDate_[^>]*>(\d{2})\.(\d{2})", row)
        if date_match:
            current_day = int(date_match.group(2))
        if current_day is None:
            continue
        game_date = date(year, month, current_day)
        if game_date > through:
            continue
        play = re.search(r'<td class="play">(.*?)</td>', row, flags=re.S | re.I)
        if not play:
            continue
        matchup = re.search(
            r'^\s*<span[^>]*>([^<]+)</span>\s*<em>(.*?)</em>\s*<span[^>]*>([^<]+)</span>',
            play.group(1), flags=re.S | re.I,
        )
        if not matchup:
            continue
        scores = [int(value) for value in re.findall(r"<span[^>]*>(\d+)</span>", matchup.group(2))]
        if len(scores) != 2:
            continue
        yield {
            "date": game_date.isoformat(),
            "away": text_content(matchup.group(1)), "awayScore": scores[0],
            "home": text_content(matchup.group(3)), "homeScore": scores[1],
        }


def read_existing_payload(target: Path) -> dict | None:
    if not target.exists():
        return None
    prefix = "window.KBO_DATA = "
    try:
        content = target.read_text(encoding="utf-8")
        if not content.startswith(prefix):
            return None
        return json.loads(content[len(prefix):].removesuffix(";\n"))
    except (OSError, json.JSONDecodeError):
        return None


def write_atomically(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=target.parent, prefix=".data-", suffix=".js")
    try:
        os.fchmod(descriptor, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def data_target() -> Path:
    return Path(os.environ.get(
        "KBO_DATA_PATH",
        Path(__file__).resolve().parents[1] / "runtime" / "data.js",
    ))


def main() -> dict:
    # 컨테이너의 기본 시간대(대개 UTC)와 관계없이 KBO 기준일은 한국 날짜로 잡는다.
    today = datetime.now(KST).date()
    year = today.year
    client = opener()
    standings = {key: parse_standings(fetch(client, url)) for key, url in RANK_URLS.items()}
    initial = fetch(client, SCHEDULE_URL)

    remaining = {name: 0 for league in standings.values() for name in [t["name"] for t in league]}
    games = []
    last_results = {}
    for month in range(today.month, 13):
        page = initial if month == today.month else month_page(client, initial, year, month)
        for game_date, away, home in parse_remaining_games(page, year, month, today):
            games.append({"date": game_date.isoformat(), "away": away, "home": home})
            if away in remaining:
                remaining[away] += 1
            if home in remaining:
                remaining[home] += 1

    all_teams = set(remaining)
    for month in range(today.month, 2, -1):
        page = initial if month == today.month else month_page(client, initial, year, month)
        completed = list(parse_completed_games(page, year, month, today))
        for game in reversed(completed):
            for name in (game["away"], game["home"]):
                if name in all_teams and name not in last_results:
                    last_results[name] = game
        if len(last_results) == len(all_teams):
            break

    for teams in standings.values():
        for team in teams:
            team["remain"] = remaining[team["name"]]

    payload = {
        "sourceDate": today.isoformat(),
        "leagues": {
            "north": {"title": "북부리그", "english": "NORTH LEAGUE", "color": "#174ea6", "teams": standings["north"]},
            "south": {"title": "남부리그", "english": "SOUTH LEAGUE", "color": "#e8472f", "teams": standings["south"]},
        },
        "remainingGames": games,
        "lastResults": last_results,
    }
    target = data_target()
    existing = read_existing_payload(target)
    comparable_existing = dict(existing) if existing else None
    if comparable_existing:
        comparable_existing.pop("updated", None)
    if comparable_existing == payload:
        target.chmod(0o644)
        print(f"{target}: 변경 없음")
        return existing

    payload = {
        "updated": datetime.now(KST).isoformat(timespec="seconds"),
        **payload,
    }
    content = "window.KBO_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n"
    write_atomically(target, content)
    print(f"{target}: {len(games)}경기, {sum(remaining.values()) // 2}경기 집계 · 갱신 완료")
    return payload


refresh_lock = threading.Lock()


class RefreshHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/refresh":
            self.send_error(404)
            return
        try:
            with refresh_lock:
                payload = main()
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as error:
            body = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"refresh-api: {format % args}")


def serve():
    main()

    def scheduled_updates():
        while True:
            threading.Event().wait(21600)
            try:
                with refresh_lock:
                    main()
            except Exception as error:
                print(f"자동 갱신 실패: {error}")

    threading.Thread(target=scheduled_updates, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8000), RefreshHandler).serve_forever()


if __name__ == "__main__":
    serve() if "--serve" in os.sys.argv else main()
