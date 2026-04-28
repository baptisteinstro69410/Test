from pathlib import Path
import json
import re
import pandas as pd
from datetime import datetime

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / 'sources'
OUT_DIR = ROOT / 'data'
OUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUT_DIR / 'controles.json'

SUPPORTED = {'.xlsx', '.xls', '.csv', '.txt'}

def normalize(v):
    return str(v or '').strip().upper().replace(' ', '').replace(' ', '').replace('	', '').replace('
', '')

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
    return dt.strftime('%d/%m/%Y %H:%M:%S')

def detect_indices(headers):
    H = [str(h or '').strip().upper() for h in headers]
    def find(names):
        for n in names:
            if n in H:
                return H.index(n)
        return -1
    sn_idx = find(['NS BATTERIE','NS','NS (V)','SN','SN (V)','SERIAL','SERIALNUMBER','NUMERO DE SERIE','N° SERIE'])
    date_idx = find(['HEURE DE DÉBUT','HEURE DE DEBUT','DATE','DATE CONTROLE','DATE DE CONTROLE','DATE DE CONTRÔLE'])
    return (sn_idx if sn_idx >= 0 else 5, date_idx if date_idx >= 0 else 1)

def merge_record(items, key, record):
    cur = items.get(key)
    if not cur:
        items[key] = record
        return
    cur_iso = cur.get('controlDateIso') or ''
    new_iso = record.get('controlDateIso') or ''
    if new_iso > cur_iso:
        items[key] = record

def detect_source(file_name, sheet_name):
    u = (file_name + ' ' + sheet_name).upper()
    if 'BAT' in u:
        return 'BATTERIE'
    if 'BJONG' in u:
        return 'BJONG'
    return 'CONTROLE'

def process_csv_or_txt(path, items):
    text = path.read_text(encoding='utf-8', errors='ignore')
    for idx, line in enumerate(re.split(r'?
', text)):
        cols = re.split(r'[,;	]', line)
        raw_sn = cols[5] if len(cols) > 5 else (cols[2] if len(cols) > 2 else '')
        raw_dt = cols[1] if len(cols) > 1 else (cols[0] if len(cols) > 0 else '')
        key = canonical_sn(raw_sn)
        if not key:
            continue
        if idx == 0 and key in {'SN','SERIAL','SERIALNUMBER','NUMERODESERIE','N°SERIE','NSBATTERIE','NS'}:
            continue
        dt = parse_dt_any(raw_dt)
        merge_record(items, key, {
            'display': normalize(raw_sn),
            'source': detect_source(path.name, ''),
            'controlDateIso': dt.isoformat() if dt else '',
            'controlDateText': format_fr(dt) if dt else '',
            'sheet': '',
            'file': path.name,
        })

def process_excel(path, items):
    xl = pd.ExcelFile(path, engine='openpyxl')
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, engine='openpyxl')
        headers = list(df.columns)
        sn_idx, date_idx = detect_indices(headers)
        for _, row in df.iterrows():
            vals = list(row.values.tolist())
            raw_sn = vals[sn_idx] if sn_idx < len(vals) else ''
            raw_dt = vals[date_idx] if date_idx < len(vals) else ''
            key = canonical_sn(raw_sn)
            if not key:
                continue
            dt = parse_dt_any(raw_dt)
            merge_record(items, key, {
                'display': normalize(raw_sn),
                'source': detect_source(path.name, sheet),
                'controlDateIso': dt.isoformat() if dt else '',
                'controlDateText': format_fr(dt) if dt else '',
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
        if path.suffix.lower() in {'.csv','.txt'}:
            process_csv_or_txt(path, items)
        else:
            process_excel(path, items)
    payload = {
        'generatedAt': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'items': items
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(items)} SN exportés vers {OUT_FILE}')

if __name__ == '__main__':
    main()
