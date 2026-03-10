from preprocessing import (
    load_dataset,
    clean_dataset,
    feature_engineering,
    handle_outliers,
    save_processed_dataset
)

from config import RAW_DATA_PATH, PROCESSED_DATA_PATH


def run_pipeline():

    print("Loading dataset...")
    df = load_dataset(RAW_DATA_PATH)

    print("Cleaning dataset...")
    df = clean_dataset(df)

    print("Handling outliers...")
    df = handle_outliers(df)

    print("Creating features...")
    df = feature_engineering(df)

    print("Saving processed dataset...")
    save_processed_dataset(df, PROCESSED_DATA_PATH)

    print("Pipeline completed successfully")

if __name__ == "__main__":
    run_pipeline()
    