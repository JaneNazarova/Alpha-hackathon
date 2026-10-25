# Исследует состав и качество исходных таблиц.
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from ml.company_profile import FIELDS
from ml.data_access import boolean, iter_csv, number


def describe(rows, key=None, *, observe=None, duplicate_rows=False):
    counts, numeric, invalid_flags = {}, {}, Counter()
    revenue, n, fingerprints = [], 0, set()
    flag_columns = {c for f, c in FIELDS.items() if f.startswith('has_')}
    for row in rows:
        n += 1
        if observe:
            observe(row)
        if duplicate_rows:
            fingerprints.add(hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).digest())
        for column, value in row.items():
            if column not in counts:
                counts[column], numeric[column] = Counter(), True
            if value is None:
                continue
            counts[column][value] += 1
            value_num = number(value)
            if value_num is None:
                numeric[column] = False
            if column == 'REVENUE_COMPANY' and value_num is not None and value_num >= 0:
                revenue.append(value_num)
            if column in flag_columns and boolean(value) is None:
                invalid_flags[column] += 1
    result = {'rows': n, 'columns': {}, 'key': key}
    for column, counter in counts.items():
        known = sum(counter.values())
        stats = {'missing': n-known, 'missing_fraction': (n-known)/n if n else 0.,
                 'unique': len(counter), 'inferred_type': 'numeric' if known and numeric[column] else 'categorical_or_text'}
        if column in {'MAINOKVED_CODE', 'MAINOKVED_NAME', 'REGION', 'FTS_COUNTRY_NAME', 'COMPANY_AGE_YEARS_GRADATION', 'ECO_MARK_LABEL'} or column.startswith('CL_PRODUCT_') or column in {'FTS_FLAG', 'FACTORING_MARK'}:
            stats['top_values'] = counter.most_common(15)
        if column in flag_columns:
            stats['invalid_booleans'] = invalid_flags[column]
        if column == 'REVENUE_COMPANY':
            revenue.sort()
            stats['distribution'] = {'valid': len(revenue), 'invalid': known-len(revenue),
                'min': revenue[0] if revenue else None,
                'median': (revenue[(len(revenue)-1)//2]+revenue[len(revenue)//2])/2 if revenue else None,
                'p25': revenue[int((len(revenue)-1)*.25)] if revenue else None,
                'p75': revenue[int((len(revenue)-1)*.75)] if revenue else None,
                'max': revenue[-1] if revenue else None, 'above_15bn': sum(v > 15e9 for v in revenue)}
        result['columns'][column] = stats
    if key:
        counter = counts.get(key, {})
        result['key_quality'] = {'missing': n-sum(counter.values()), 'unique': len(counter),
                                 'duplicate_rows': sum(v-1 for v in counter.values()),
                                 'duplicate_ids': sum(v>1 for v in counter.values())}
    if duplicate_rows:
        result['duplicate_records'] = n-len(fingerprints)
        result['duplicate_detection'] = 'SHA-256 of normalized complete row'
    return result


def analyze(companies, payments=None, person_links=None):
    ids = set()
    result = {'companies': describe(companies, 'SYNTHETIC_U', observe=lambda r: ids.add(r.get('SYNTHETIC_U'))),
              'payments': None, 'person_links': None,
              'limitations': ['No market denominator: market share cannot be estimated.',
                              'Payment exposure is observed only in supplied table; period/coverage may be unknown.']}
    ids.discard(None)
    if payments is not None:
        ends, bad, missing_keys = set(), Counter(), Counter()
        self_rows = 0
        def payment_observer(row):
            nonlocal self_rows
            payer, payee = row.get('PAYER'), row.get('BENEFICIARY')
            ends.update((payer, payee))
            self_rows += payer is not None and payer == payee
            for column in ('PAYER', 'BENEFICIARY'):
                if row.get(column) is None:
                    missing_keys[column] += 1
            for column in ('PAY_AMT', 'PAY_CNT'):
                value = number(row.get(column))
                bad[column] += value is None or value < 0 or (column == 'PAY_CNT' and not value.is_integer())
        result['payments'] = describe(payments, observe=payment_observer, duplicate_rows=True)
        ends.discard(None)
        result['payments'].update(known_company_coverage=len(ends & ids)/len(ids) if ids else 0.,
            unique_endpoints=len(ends), unknown_endpoints=len(ends-ids), invalid_amounts=bad['PAY_AMT'],
            invalid_counts=bad['PAY_CNT'], missing_endpoint_cells=dict(missing_keys), self_payment_rows=self_rows)
    if person_links is not None:
        edges, linked_ids = set(), set()
        unknown, missing_person = 0, 0
        def link_observer(row):
            nonlocal unknown, missing_person
            person, company_id = row.get('SYNTHETIC_F'), row.get('SYNTHETIC_U')
            edges.add((person, company_id))
            linked_ids.add(company_id)
            unknown += company_id not in ids
            missing_person += person is None
        result['person_links'] = describe(person_links, observe=link_observer)
        result['person_links'].update(unknown_companies=unknown, missing_person_ids=missing_person,
            known_company_coverage=len(linked_ids & ids)/len(ids) if ids else 0.,
            duplicate_edges=result['person_links']['rows']-len(edges))
    return result


def main():
    parser = argparse.ArgumentParser(description='Reproducible streaming diagnostics for companies, links and payments.')
    parser.add_argument('--companies', required=True)
    parser.add_argument('--payments')
    parser.add_argument('--person-links')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = analyze(iter_csv(args.companies), iter_csv(args.payments) if args.payments else None,
                     iter_csv(args.person_links) if args.person_links else None)
    result['input_files'] = {k: str(v) for k, v in vars(args).items() if k != 'output' and v}
    result['input_sha256'] = {}
    for key, path in result['input_files'].items():
        with Path(path).open('rb') as source:
            result['input_sha256'][key] = hashlib.file_digest(source, 'sha256').hexdigest()
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k]['rows'] if result[k] else None for k in ('companies', 'payments', 'person_links')}))


if __name__ == '__main__':
    main()
