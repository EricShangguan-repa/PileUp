import pandas as pd

NON_PRODUCT_CODES = {"POST", "D", "M", "DOT", "BANK CHARGES", "AMAZONFEE", "C2"}

RAW_COLUMNS = [
    "Invoice",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "Price",
    "Customer ID",
    "Country",
]


def is_cancellation(invoice: str) -> bool:
    return str(invoice).strip().upper().startswith("C")


def is_non_product_code(stock_code: str) -> bool:
    return str(stock_code).strip().upper() in NON_PRODUCT_CODES


def clean_online_retail(df: pd.DataFrame) -> pd.DataFrame:
    """Clean raw Online Retail II rows per the documented rules:
    - normalize StockCode to uppercase (the same product appears under both
      cases, e.g. '72349B' and '72349b', for 173 stock codes in the raw data)
    - drop cancellations (Invoice starts with 'C') entirely, don't net them out
    - drop non-product stock codes (postage, manual adjustments, fees, etc.)
    - drop rows with Price <= 0 or Quantity <= 0
    - keep rows with missing Customer ID (valid for demand forecasting)
    """
    df = df.copy()
    df["Invoice"] = df["Invoice"].astype(str)
    df["StockCode"] = df["StockCode"].astype(str).str.upper()

    df = df[~df["Invoice"].apply(is_cancellation)]
    df = df[~df["StockCode"].apply(is_non_product_code)]
    df = df[(df["Price"] > 0) & (df["Quantity"] > 0)]

    return df.reset_index(drop=True)
