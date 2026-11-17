import pandas as pd

from pipeline.transform import clean_online_retail, is_cancellation, is_non_product_code


def _row(**overrides):
    base = {
        "Invoice": "536365",
        "StockCode": "85123A",
        "Description": "WHITE HANGING HEART T-LIGHT HOLDER",
        "Quantity": 6,
        "InvoiceDate": pd.Timestamp("2010-12-01 08:26:00"),
        "Price": 2.55,
        "Customer ID": 17850,
        "Country": "United Kingdom",
    }
    base.update(overrides)
    return base


def test_is_cancellation():
    assert is_cancellation("C536379")
    assert not is_cancellation("536365")


def test_is_non_product_code():
    assert is_non_product_code("POST")
    assert is_non_product_code("bank charges")
    assert not is_non_product_code("85123A")


def test_drops_cancellations():
    df = pd.DataFrame([_row(), _row(Invoice="C536379", Quantity=-1)])
    cleaned = clean_online_retail(df)
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["Invoice"] == "536365"


def test_drops_non_product_codes():
    df = pd.DataFrame([_row(), _row(StockCode="POST", Description="POSTAGE")])
    cleaned = clean_online_retail(df)
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["StockCode"] == "85123A"


def test_drops_non_positive_price_or_quantity():
    df = pd.DataFrame(
        [
            _row(),
            _row(Price=0.0),
            _row(Price=-5.0),
            _row(Quantity=0),
            _row(Quantity=-3),
        ]
    )
    cleaned = clean_online_retail(df)
    assert len(cleaned) == 1


def test_keeps_missing_customer_id():
    df = pd.DataFrame([_row(**{"Customer ID": None})])
    cleaned = clean_online_retail(df)
    assert len(cleaned) == 1


def test_normalizes_stock_code_case():
    df = pd.DataFrame(
        [
            _row(Invoice="1", StockCode="72349B"),
            _row(Invoice="2", StockCode="72349b"),
        ]
    )
    cleaned = clean_online_retail(df)
    assert set(cleaned["StockCode"]) == {"72349B"}
