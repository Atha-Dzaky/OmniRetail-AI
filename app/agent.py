import re
import calendar
from datetime import date
from typing import Optional
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from sqlalchemy import text

from app.db import engine
import json
from datetime import datetime
from pathlib import Path


MONTHS_ID = {
    'januari': 1, 'februari': 2, 'maret': 3, 'april': 4, 'mei': 5, 'juni': 6,
    'juli': 7, 'agustus': 8, 'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
}

MONTHS_EN = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}


def parse_platform(text_str: str) -> Optional[str]:
    m = re.search(r"\b(amazon|tokopedia|shopee|lazada)\b", text_str, re.IGNORECASE)
    return m.group(1).capitalize() if m else None


def parse_month_year(text_str: str) -> Optional[tuple]:
    # look for patterns like 'Mei 2022' or 'May 2022'
    m = re.search(r"([A-Za-z]+)\s+(\d{4})", text_str)
    if m:
        mon = m.group(1).lower()
        year = int(m.group(2))
        if mon in MONTHS_ID:
            month = MONTHS_ID[mon]
            return month, year
        if mon in MONTHS_EN:
            month = MONTHS_EN[mon]
            return month, year
    return None


def build_sql(platform: Optional[str], month_year: Optional[tuple]) -> tuple[str, dict]:
    params = {}
    where_clauses = []
    if platform:
        where_clauses.append("platform = :platform")
        params['platform'] = platform

    if month_year:
        month, year = month_year
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        where_clauses.append("order_date >= :start_date AND order_date <= :end_date")
        params['start_date'] = start
        params['end_date'] = end

    where_sql = (' WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
    sql = f"SELECT SUM(quantity) AS total_quantity FROM sales_transactions{where_sql};"
    return sql, params


def run_agent_question(question: str):
    platform = parse_platform(question)
    month_year = parse_month_year(question)

    sql, params = build_sql(platform, month_year)
    print('Generated SQL:')
    print(sql)
    print('\nParams:', params)

    with engine.begin() as conn:
        res = conn.execute(text(sql), params)
        row = res.fetchone()
        total = row[0] if row is not None else None
    result = {'question': question, 'total_quantity': int(total) if total is not None else 0}
    print('\nResult:')
    print(result)

    # write to JSONL log
    try:
        log_dir = Path(ROOT_DIR) / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'agent_queries.jsonl'
        entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'question': question,
            'sql': sql,
            'params': {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in params.items()},
            'result': result,
        }
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        print(f"Logged query to {log_file}")
    except Exception as e:
        print('Failed to write log:', e)


if __name__ == '__main__':
    # example question (Indonesian)
    q = "Berapa total quantity penjualan dari platform Amazon pada bulan Mei 2022?"
    run_agent_question(q)
