import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

import main
import pandas as pd


def test_find_supervised_label_column_exact_is_fraud():
    df = pd.DataFrame({"is_fraud": [0, 1, 0]})
    col, explicit = main._find_supervised_label_column(df)
    assert col == "is_fraud"
    assert explicit is True


def test_find_supervised_label_column_case_insensitive():
    df = pd.DataFrame({"IS_FRAUD": [0, 1]})
    col, explicit = main._find_supervised_label_column(df)
    assert col == "IS_FRAUD"
    assert explicit is True


def test_find_supervised_label_column_with_spaces():
    df = pd.DataFrame({" is_fraud ": [0, 1]})
    col, explicit = main._find_supervised_label_column(df)
    assert col == " is_fraud "
    assert explicit is True


if __name__ == "__main__":
    test_find_supervised_label_column_exact_is_fraud()
    test_find_supervised_label_column_case_insensitive()
    test_find_supervised_label_column_with_spaces()
    print("PASS: label detection tests")
