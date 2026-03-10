from preprocessing import (
    load_dataset,
    clean_dataset,
    feature_engineering,
    handle_outliers,
    save_processed_dataset
)

from config import RAW_DATA_PATH, PROCESSED_DATA_PATH
from data_validation import run_data_validation
from logger import get_logger, generate_run_id
logger = get_logger()
from s3_utils import upload_file

def run_pipeline():

    run_id = generate_run_id()

    try:

        logger.info(f"RUN_ID={run_id} | Pipeline started")

        logger.info(f"RUN_ID={run_id} | Loading dataset")
        df = load_dataset(RAW_DATA_PATH)

        logger.info(f"RUN_ID={run_id} | Uploading raw dataset to S3")
        upload_file(
            RAW_DATA_PATH,
            "raw-data/retail_store_inventory.csv"
        )

        logger.info(f"RUN_ID={run_id} | Cleaning dataset")
        df = clean_dataset(df)

        logger.info(f"RUN_ID={run_id} | Running data validation")
        run_data_validation(df)

        logger.info(f"RUN_ID={run_id} | Handling outliers")
        df = handle_outliers(df)

        logger.info(f"RUN_ID={run_id} | Creating features")
        df = feature_engineering(df)

        logger.info(f"RUN_ID={run_id} | Saving processed dataset")
        save_processed_dataset(df, PROCESSED_DATA_PATH)

        logger.info(f"RUN_ID={run_id} | Uploading processed dataset to S3")
        upload_file(
            PROCESSED_DATA_PATH,
            "processed-data/processed_sales_data.csv"
        )

        logger.info(f"RUN_ID={run_id} | Pipeline completed successfully")

    except Exception as e:

        logger.error(f"RUN_ID={run_id} | Pipeline failed: {str(e)}")
        raise

if __name__ == "__main__":
    run_pipeline()

