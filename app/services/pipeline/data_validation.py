EXPECTED_COLUMNS = [
    "date",
    "store_id",
    "product_id",
    "category",
    "region",
    "inventory_level",
    "units_sold",
    "units_ordered",
    "demand_forecast",
    "price",
    "discount",
    "weather_condition",
    "holiday_promotion",
    "competitor_pricing",
    "seasonality"
]

def validate_columns(df):

    missing_columns = []

    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            missing_columns.append(col)

    if len(missing_columns) > 0:
        raise ValueError(f"Missing required columns: {missing_columns}")

    print("Schema validation passed")

def validate_data_types(df):

    numeric_columns = [
        "inventory_level",
        "units_sold",
        "units_ordered",
        "price",
        "discount",
        "competitor_pricing"
    ]

    for col in numeric_columns:

        if not df[col].dtype in ["int64", "float64"]:
            print(f"Warning: Column {col} is not numeric")

    print("Data type validation completed")

def validate_value_ranges(df):

    if (df["price"] < 0).any():
        print("Warning: Negative prices detected")

    if (df["units_sold"] < 0).any():
        print("Warning: Negative sales detected")

    if (df["discount"] > 100).any():
        print("Warning: Discount above 100% detected")

    print("Value range validation completed")

def run_data_validation(df):

    print("Running schema validation...")

    validate_columns(df)

    validate_data_types(df)

    validate_value_ranges(df)

    print("All validation checks completed")

