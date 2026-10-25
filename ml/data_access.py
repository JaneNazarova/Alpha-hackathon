# Читает CSV и очищает числа, флаги и пропуски.
import csv
import codecs
import math
from pathlib import Path

MISSING = {"", "null", "none", "nan", "na", "n/a", "нет данных", "неизвестно"}


def clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return None if value.casefold() in MISSING else value


def number(value):
    value = clean(value)
    if value is None:
        return None
    try:
        result = float(value.replace("\u00a0", "").replace(" ", "").replace(",", "."))
        return result if math.isfinite(result) else None
    except ValueError:
        return None


def boolean(value):
    value = clean(value)
    if value is None:
        return None
    if value.casefold() in {"1", "1.0", "true", "yes", "да", "y"}:
        return True
    if value.casefold() in {"0", "0.0", "false", "no", "нет", "n"}:
        return False
    return None


def iter_csv(path):
    with Path(path).open("rb") as source:
        sample = source.read(65536)
    try:
        text = codecs.getincrementaldecoder("utf-8-sig")().decode(sample, final=False)
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        text = sample.decode("cp1251")
        encoding = "cp1251"
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if ";" in text.partition("\n")[0] else ","
    with Path(path).open(encoding=encoding, newline="") as source:
        reader = csv.DictReader(source, delimiter=delimiter)
        if not reader.fieldnames or len({k.strip().upper() for k in reader.fieldnames}) != len(reader.fieldnames):
            raise ValueError("CSV needs unique column names")
        for line, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"CSV has incorrect cell count at line {line}")
            yield {k.strip().upper(): clean(v) for k, v in row.items()}


def read_csv(path):
    return list(iter_csv(path))
