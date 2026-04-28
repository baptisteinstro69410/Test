from pathlib import Path
import json
import re
import pandas as pd
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / 'sources'
OUT_DIR = ROOT / 'data'
OUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUT_DIR / 'controles.json'
SUPPORTED = {'.xlsx', '.xls', '.csv', '.txt'}


def clean_text(v):
    if pd.isna(v):
        return ''
    return str(v).strip().replace('\u00A0', ' ')


def normalize(v):
    return clean_text(v).upper().replace(' ', '').replace('\t', '').replace('\n', '')


def canonical_sn(v):
    s = normalize(v)
    return re.sub(r'^V(?=.+)', '', s)


def parse_dt_any(v):
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    s = str(v).strip()
    if not s:
        return None
    for dayfirst in (True, False):
        try:
            dt = pd.to_datetime(s, dayfirst=dayfirst, errors='raise')
            if pd.isna(dt):
                continue
            return dt.to_pydatetime()
        except Exception:
            pass
    return None


def format_fr(dt):
    return dt.strftime('%d/%m/%Y %H:%M:%S') if dt else ''


def detect_source(file_name, sheet_name):
    u = f'{file_name} {sheet_name}'.upper()
    if 'BAT' in u:
        return 'BATTERIE'
    if 'BJONG' in u:
        return 'BJONG'
    return 'CONTROLE'


def detect_indices_from_headers(headers):
    H = [clean_text(h).upper() for h in headers]
    def find(names):
        for n in names:
            for i, h in enumerate(H):
                if h == n:
                    return i
        return -1
    sn_idx = find(['NS BATTERIE','NS','NS (V)','SN','SN (V)','SERIAL','SERIALNUMBER','NUMERO DE SERIE','N° SERIE'])
    date_idx = find(['HEURE DE DÉBUT','HEURE DE DEBUT','DATE','DATE CONTROLE','DATE DE CONTROLE','DATE DE CONTRÔLE'])
    return sn_idx, date_idx


def choose_indices_from_data(df):
    sample = df.head(20)
    cols = list(df.columns)
    sn_idx = -1
    date_idx = -1

    for i, col in enumerate(cols):
        vals = [canonical_sn(v) for v in sample[col].tolist()]
        vals = [v for v in vals if v]
        if vals and sum(v.isdigit() and len(v) >= 6 for v in vals) >= max(1, len(vals) // 2):
            sn_idx = i
            break

    for i, col in enumerate(cols):
        vals = sample[col].tolist()
        parsed = [parse_dt_any(v) for v in vals]
        ok = sum(v is not None for v in parsed)
        if ok >= max(1, len(vals) // 2):
            date_idx = i
            break

    if sn_idx < 0 and len(cols) > 5:
        sn_idx = 5
    elif sn_idx < 0:
        sn_idx = 0
    if date_idx < 0 and len(cols) > 1:
        date_idx = 1
    elif date_idx < 0:
        date_idx = 0
    return sn_idx, date_idx


def merge_record(items, key, record):
    cur = items.get(key)
    if not cur:
        items[key] = record
        return
    cur_iso = cur.get('controlDateIso') or ''
    new_iso = record.get('controlDateIso') or ''
    if new_iso > cur_iso:
        items[key] = record


def process_csv_or_txt(path, items):
    text = path.read_text(encoding='utf-8', errors='ignore')
    rows = [re.split(r'[,;\t]', line) for line in re.split(r'\r?\n', text) if line.strip()]
    if not rows:
        return
    header = rows[0]
    sn_idx, date_idx = detect_indices_from_headers(header)
    if sn_idx < 0 or date_idx < 0:
        sn_idx = 5 if len(header) > 5 else (2 if len(header) > 2 else 0)
        date_idx = 1 if len(header) > 1 else 0
    for idx, cols in enumerate(rows):
        raw_sn = cols[sn_idx] if sn_idx < len(cols) else ''
        raw_dt = cols[date_idx] if date_idx < len(cols) else ''
        key = canonical_sn(raw_sn)
        if not key:
            continue
        if idx == 0 and normalize(raw_sn) in {'SN','SERIAL','SERIALNUMBER','NUMERODESERIE','N°SERIE','NSBATTERIE','NS'}:
            continue
        if key.isdigit() and len(key) < 6:
            continue
        dt = parse_dt_any(raw_dt)
        merge_record(items, key, {
            'display': normalize(raw_sn),
            'source': detect_source(path.name, ''),
            'controlDateIso': dt.isoformat() if dt else '',
            'controlDateText': format_fr(dt),
            'sheet': '',
            'file': path.name,
        })


def process_excel(path, items):
    xl = pd.ExcelFile(path, engine='openpyxl')
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, engine='openpyxl')
        sn_idx, date_idx = detect_indices_from_headers(list(df.columns))
        if sn_idx < 0 or date_idx < 0:
            sn_idx, date_idx = choose_indices_from_data(df)
        for _, row in df.iterrows():
            vals = row.tolist()
            raw_sn = vals[sn_idx] if sn_idx < len(vals) else ''
            raw_dt = vals[date_idx] if date_idx < len(vals) else ''
            key = canonical_sn(raw_sn)
            if not key:
                continue
            if key.isdigit() and len(key) < 6:
                continue
            dt = parse_dt_any(raw_dt)
            merge_record(items, key, {
                'display': normalize(raw_sn),
                'source': detect_source(path.name, sheet),
                'controlDateIso': dt.isoformat() if dt else '',
                'controlDateText': format_fr(dt),
                'sheet': sheet,
                'file': path.name,
            })


def main():
    items = {}
    if not SOURCE_DIR.exists():
        raise SystemExit(f'Dossier sources absent: {SOURCE_DIR}')
    files = [p for p in SOURCE_DIR.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED]
    if not files:
        raise SystemExit('Aucun fichier source trouvé dans /sources')
    for path in files:
        if path.suffix.lower() in {'.csv', '.txt'}:
            process_csv_or_txt(path, items)
        else:
            process_excel(path, items)
    payload = {
        'generatedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'count': len(items),
        'items': items
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(items)} SN exportés vers {OUT_FILE}')


if __name__ == '__main__':
    main()
