"""Refresh public UN Careers data for Pages. No credentials or visitor data."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import ssl
import urllib.request
from zoneinfo import ZoneInfo

URL = 'https://careers.un.org/api/public/opening/jo/list/filteredV2/en'
PREVIOUS_FEED = 'https://audreyyuan0825.github.io/international-career-explorer-site/vacancies.json'


def fetch(page):
    request = urllib.request.Request(URL, data=json.dumps({
        'filterConfig': {'jle': [], 'jc': []}, 'pagination': {
            'page': page, 'itemPerPage': 500, 'sortBy': 'jobId', 'sortDirection': -1}
    }).encode(), headers={'Content-Type': 'application/json'})
    ca = '/etc/ssl/cert.pem' if Path('/etc/ssl/cert.pem').exists() else None
    with urllib.request.urlopen(request, timeout=30, context=ssl.create_default_context(cafile=ca)) as response:
        body = response.read(12_000_001)
    if len(body) > 12_000_000:
        raise ValueError('Vacancy feed exceeds size limit')
    data = json.loads(body)
    if data.get('status') != 1 or not isinstance(data.get('data', {}).get('list'), list):
        raise ValueError('UN Careers feed is unavailable')
    return data['data']


def previous_rows(output):
    """Read our last published official snapshot; it contains no visitor information."""
    feeds = []
    if output.exists():
        try:
            feeds.append(json.loads(output.read_text()))
        except (OSError, ValueError):
            pass
    try:
        ca = '/etc/ssl/cert.pem' if Path('/etc/ssl/cert.pem').exists() else None
        request = urllib.request.Request(PREVIOUS_FEED, headers={'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=20, context=ssl.create_default_context(cafile=ca)) as response:
            raw = response.read(25_000_001)
        if len(raw) <= 25_000_000:
            feeds.append(json.loads(raw))
    except (OSError, ValueError):
        pass  # Current openings can still refresh; a missing archive is not invented.
    rows = []
    for feed in feeds:
        if feed.get('schema') != 1 or feed.get('source') != 'UN Careers':
            continue
        for key in ['vacancies', 'archived_vacancies']:
            values = feed.get(key, [])
            if isinstance(values, list) and len(values) <= 2000:
                rows.extend({**row, 'last_seen_at': row.get('last_seen_at') or feed.get('updated_at')}
                            for row in values if isinstance(row, dict))
    return rows


def archive_rows(rows, active_ids, today):
    """Retain up to 1,000 dated examples from the last 180 days, separately from live jobs."""
    earliest = (datetime.fromisoformat(today).date() - timedelta(days=180)).isoformat()
    unique = {}
    keys = ['jobId', 'categoryCode', 'jobLevel', 'postingTitle', 'jobTitle',
            'jobDescription', 'jf', 'dept', 'dutyStation', 'recrttype', 'endDate',
            'deadline_date', 'last_seen_at']
    for row in rows:
        job_id, due = str(row.get('jobId', '')), row.get('deadline_date', '')
        try:
            datetime.strptime(due, '%Y-%m-%d')
        except (ValueError, TypeError):
            continue
        if job_id.isdigit() and job_id not in active_ids and earliest <= due < today:
            unique[job_id] = {k: row.get(k) for k in keys}
    return sorted(unique.values(), key=lambda r: r['deadline_date'], reverse=True)[:1000]


def refresh(output):
    previous = previous_rows(output)
    first = fetch(0)
    rows = first['list']
    count = int(first.get('count', len(rows)))
    if count > 2000:
        raise ValueError('Unexpected vacancy count')
    with ThreadPoolExecutor(max_workers=3) as pool:
        for data in pool.map(fetch, range(1, (count + 499) // 500)):
            rows.extend(data['list'])
    clean = {}
    keys = ['jobId', 'categoryCode', 'jobLevel', 'postingTitle', 'jobTitle',
            'jobDescription', 'jf', 'dept', 'dutyStation', 'recrttype', 'endDate']
    today = datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    for row in rows:
        try:
            if not str(row['jobId']).isdigit():
                continue
            due = datetime.fromisoformat(row['endDate'].replace('Z', '+00:00')).astimezone(
                ZoneInfo('America/New_York')).date().isoformat()
            if due < today:
                continue
            clean[row['jobId']] = {**{k: row.get(k) for k in keys}, 'deadline_date': due}
        except (KeyError, TypeError, ValueError):
            continue
    if not clean:
        raise ValueError('Refusing to replace feed with an empty response')
    archive = archive_rows(previous, {str(k) for k in clean}, today)
    result = {'schema': 1, 'source': 'UN Careers',
              'archived_vacancies': archive, 'archive_days': 180,
              'updated_at': datetime.now(timezone.utc).isoformat(), 'vacancies': list(clean.values())}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding='utf8')
    temporary.replace(output)
    print(f'Refreshed {len(clean)} public vacancies; retained {len(archive)} closed reference notices')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('vacancies.json'))
    refresh(parser.parse_args().output)
