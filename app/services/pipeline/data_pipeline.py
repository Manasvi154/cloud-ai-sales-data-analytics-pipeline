import os

from .preprocessing import (
    load_dataset,
    clean_dataset,
    feature_engineering,
    handle_outliers,
    save_processed_dataset
)

from .data_validation import run_data_validation
from .logger import get_logger, generate_run_id
logger = get_logger()
from .s3_utils import upload_file

def run_pipeline(file_path):

    run_id = generate_run_id()

    try:

        logger.info(f"RUN_ID={run_id} | Pipeline started")

        logger.info(f"RUN_ID={run_id} | Loading dataset")
        df = load_dataset(file_path)

        logger.info(f"RUN_ID={run_id} | Uploading raw dataset to S3")
        upload_file(
            file_path,
            f"raw-data/{os.path.basename(file_path)}"
        )

        logger.info(f"RUN_ID={run_id} | Cleaning dataset")
        df = clean_dataset(df)

        logger.info(f"RUN_ID={run_id} | Running data validation")
        run_data_validation(df)

        logger.info(f"RUN_ID={run_id} | Handling outliers")
        df = handle_outliers(df)

        logger.info(f"RUN_ID={run_id} | Creating features")
        df = feature_engineering(df)

        # ==============================
        # REAL ANALYTICS
        # ==============================

        logger.info(f"RUN_ID={run_id} | Generating analytics")

        total_rows = len(df)

        total_sales = df["units_sold"].sum()

        avg_sales = df["units_sold"].mean()

        top_category = df.groupby("category")["units_sold"].sum().idxmax()

        top_region = df.groupby("region")["units_sold"].sum().idxmax()

        monthly_sales = df.groupby("month")["units_sold"].sum().to_dict()

        # ==============================
        # INSIGHTS GENERATION
        # ==============================

        insights = []

        if avg_sales > 100:
            insights.append("Average sales are strong, indicating high product demand.")
        else:
            insights.append("Average sales are relatively low, suggesting demand improvement opportunities.")

        insights.append(f"Top performing category is {top_category}.")
        insights.append(f"Region with highest sales is {top_region}.")

        base_name = os.path.basename(file_path).replace(".csv", "")

        processed_path = f"data/processed/{base_name}_processed.csv"
        os.makedirs(os.path.dirname(processed_path), exist_ok=True)

        logger.info(f"RUN_ID={run_id} | Saving processed dataset")
        save_processed_dataset(df, processed_path)

        # Save processed dataset
        save_processed_dataset(df, processed_path)

        # Upload processed dataset
        if os.path.exists(processed_path):
            upload_file(
                processed_path,
                f"processed-data/{os.path.basename(processed_path)}"
            )
            logger.info(f"RUN_ID={run_id} | Processed dataset uploaded to S3")
        else:
            logger.error(f"RUN_ID={run_id} | Processed file missing, upload skipped")

        # ==============================
        # SAVE ANALYTICS FILE
        # ==============================

        import json

        analytics_path = file_path.replace("raw", "processed").replace(".csv", "_analytics.json")

        with open(analytics_path, "w") as f:
            json.dump({
                "metrics": {
                    "rows_processed": int(total_rows),
                    "total_sales": float(total_sales),
                    "avg_sales": float(avg_sales),
                    "top_category": str(top_category),
                    "top_region": str(top_region)
                },
                "insights": insights,
                "monthly_sales": monthly_sales
            }, f)

        logger.info(f"RUN_ID={run_id} | Analytics JSON saved")

        logger.info(f"RUN_ID={run_id} | Uploading processed dataset to S3")
        # Upload analytics JSON also
        upload_file(
            analytics_path,
            f"processed-data/{os.path.basename(analytics_path)}"
        )

        logger.info(f"RUN_ID={run_id} | Pipeline completed successfully")

    except Exception as e:

        logger.error(f"RUN_ID={run_id} | Pipeline failed: {str(e)}")
        raise

    return {
        "metrics": {
            "rows_processed": int(total_rows),
            "total_sales": float(total_sales),
            "avg_sales": float(avg_sales),
            "top_category": str(top_category),
            "top_region": str(top_region)
        },
        "insights": insights,
        "monthly_sales": monthly_sales
    }

