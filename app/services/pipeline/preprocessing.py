import pandas as pd
import numpy as np

def load_dataset(path):
    df = pd.read_csv(path)
    return df


def clean_dataset(df):

    # remove duplicate rows
    df = df.drop_duplicates()

    # standardize column names
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
    )

    # convert date column
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)

    # remove rows with invalid dates
    df = df.dropna(subset=["date"])

    # ensure numeric columns are correct
    numeric_cols = [
        "inventory_level",
        "units_sold",
        "units_ordered",
        "price",
        "discount",
        "competitor_pricing"
    ]
    print("Columns after cleaning:", df.columns.tolist())
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # remove rows where target variable is missing
    df = df.dropna(subset=["units_sold"])

    return df


def feature_engineering(df):

    # date features
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["day_of_week"] = df["date"].dt.dayofweek
    df["week_of_year"] = df["date"].dt.isocalendar().week

    # promotion flag
    df["promotion_flag"] = df["holiday_promotion"].apply(
        lambda x: 1 if str(x).lower() in ["yes", "true", "1"] else 0
    )

    # discount percentage normalization
    df["discount"] = df["discount"].fillna(0)

    return df


def handle_outliers(df):

    # remove extreme outliers from units_sold
    q1 = df["units_sold"].quantile(0.25)
    q3 = df["units_sold"].quantile(0.75)

    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    df = df[(df["units_sold"] >= lower) & (df["units_sold"] <= upper)]

    return df


def save_processed_dataset(df, path):
    import os

    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
