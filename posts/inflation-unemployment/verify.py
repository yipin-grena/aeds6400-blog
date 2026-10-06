"""Optional independent check: python3 posts/inflation-unemployment/verify.py."""
from pathlib import Path
import csv
import hashlib
import math
from collections import defaultdict

root = Path(__file__).resolve().parent

def rows(path):
    with path.open() as f:
        return list(csv.DictReader(f))

for row in rows(root / 'data/raw/provenance.csv'):
    path = root / 'data/raw' / (row['series_id'] + '.csv')
    assert hashlib.md5(path.read_bytes()).hexdigest() == row['md5']
raw = {}
for series in ('CPIAUCSL', 'UNRATE'):
    data = rows(root / 'data/raw' / (series + '.csv'))
    key = next(iter(data[0]))
    raw[series] = {r[key]: float(r[series]) for r in data}
monthly = rows(root / 'results/tables/monthly.csv')
assert len(monthly) == 120
quarters = defaultdict(list)
for row in monthly:
    date = row['date']
    prior = str(int(date[:4]) - 1) + date[4:]
    rate = 100 * (raw['CPIAUCSL'][date] / raw['CPIAUCSL'][prior] - 1)
    assert math.isclose(rate, float(row['inflation']), abs_tol=1e-10)
    assert raw['UNRATE'][date] == float(row['UNRATE'])
    quarters[(int(date[:4]), (int(date[5:7]) - 1) // 3 + 1)].append(row)
for row in rows(root / 'results/tables/quarterly.csv'):
    group = quarters[(int(row['year']), int(row['quarter']))]
    assert len(group) == 3
    for output, source in [('inflation', 'inflation'), ('unemployment', 'UNRATE')]:
        mean = sum(float(x[source]) for x in group) / 3
        assert math.isclose(mean, float(row[output]), abs_tol=1e-10)
print('Raw checksums, all 120 monthly rates, and all quarterly means verified.')

quarterly = {r['label']: r for r in rows(root / 'results/tables/quarterly.csv')}
start = max((r for r in quarterly.values() if int(r['year']) >= 2022), key=lambda r: float(r['inflation']))
end = quarterly['2024 Q4']
for row in rows(root / 'results/tables/cutoff_sensitivity.csv'):
    threshold = float(start['inflation']) - float(row['fraction']) * (float(start['inflation']) - float(end['inflation']))
    assert math.isclose(float(row['threshold']), threshold, abs_tol=1e-10)
    first = next(r for r in quarterly.values() if r['label'] > start['label'] and float(r['inflation']) <= threshold)
    assert first['label'] == row['cutoff']
    middle = quarterly[row['cutoff']]
    expected = {
        'early_inflation_drop': float(start['inflation']) - float(middle['inflation']),
        'early_unemployment_change': float(middle['unemployment']) - float(start['unemployment']),
        'later_inflation_drop': float(middle['inflation']) - float(end['inflation']),
        'later_unemployment_change': float(end['unemployment']) - float(middle['unemployment'])}
    for key, value in expected.items():
        assert math.isclose(float(row[key]), value, abs_tol=1e-10)
print('Inflation threshold selections and comparisons verified.')
