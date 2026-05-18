import os
import pandas as pd

files = [
    'backend/data/sinistres.xlsx',
    'backend/data/sinistres_20260516_094126.xlsx',
    'backend/data/contrats.xlsx',
    'backend/data/tiers.xlsx'
]

for f in files:
    print('FILE:', f)
    if not os.path.exists(f):
        print('  STATUS: MISSING')
        continue
    size = os.path.getsize(f)
    print('  SIZE:', size)
    try:
        with open(f, 'rb') as fh:
            head = fh.read(8)
        print('  MAGIC BYTES:', head)
    except Exception as e:
        print('  READ HEAD ERROR:', e)
    try:
        df = pd.read_excel(f, engine='openpyxl', nrows=2)
        print('  READ: OK — columns:', list(df.columns))
    except Exception as e:
        print('  READ ERROR:', type(e).__name__, '-', e)
    print()
