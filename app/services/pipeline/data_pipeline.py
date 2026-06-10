import os
import pandas as pd
import boto3
import time
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

def run_pipeline(file_path, operation, category="all", region="all", year="all"):

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
        # ADD YEAR COLUMN (if date exists)
        # ==============================
        if "date" in df.columns:
            df["year"] = pd.to_datetime(df["date"]).dt.year

        logger.info(f"Columns in dataset: {list(df.columns)}")

        required_columns = ["units_sold", "category", "region"]

        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
            

        # ==============================
        # REAL ANALYTICS
        # ==============================
        base_name = os.path.basename(file_path).replace(".csv", "")

        processed_path = f"data/processed/{base_name}_processed.csv"
        os.makedirs(os.path.dirname(processed_path), exist_ok=True)

        logger.info(f"RUN_ID={run_id} | Saving processed dataset")
        save_processed_dataset(df, processed_path)

        # Upload processed dataset ✅ moved here
        if os.path.exists(processed_path):
            upload_file(
                processed_path,
                f"processed/latest_data.csv"
            )

            logger.info(f"RUN_ID={run_id} | Processed dataset uploaded to S3")
        else:
            logger.error(f"RUN_ID={run_id} | Processed file missing, upload skipped")

        def refresh_quicksight_dataset():
            client = boto3.client('quicksight', region_name='ap-south-1')

            client.create_ingestion(
                DataSetId="0abf0323-3350-48a3-bd68-492599f0eb72",
                IngestionId="ingestion-" + str(int(time.time())),
                AwsAccountId="449639349013"
            )

        logger.info(f"RUN_ID={run_id} | Generating analytics")

        logger.info(f"RUN_ID={run_id} | Operation received: {operation}")

        logger.info(f"Columns in dataset: {list(df.columns)}")
        
        # ==============================
        # MODE-BASED LOGIC
        # ==============================
    

        if operation == "forecasting":

            logger.info("Running Forecasting Mode")

            # ==============================
            # SORT + GROUP DATA
            # ==============================
            df = df.sort_values("month")
            monthly_sales = df.groupby("month")["units_sold"].sum()

            # ==============================
            # BEST / WORST MONTH
            # ==============================
            best_month = monthly_sales.idxmax()
            worst_month = monthly_sales.idxmin()

            # ==============================
            # GROWTH CALCULATION
            # ==============================
            growth_rates = monthly_sales.pct_change().dropna()
            avg_growth = growth_rates.mean()

            # ==============================
            # MONTH NAME CONVERSION
            # ==============================
            month_map = {
                1: "January", 2: "February", 3: "March",
                4: "April", 5: "May", 6: "June",
                7: "July", 8: "August", 9: "September",
                10: "October", 11: "November", 12: "December"
            }

            best_month_name = month_map.get(int(best_month), str(best_month))
            worst_month_name = month_map.get(int(worst_month), str(worst_month))

            # ==============================
            # FUTURE FORECAST (6 MONTHS)
            # ==============================
            last_value = monthly_sales.iloc[-1]

            future_forecast = {}
            current_value = last_value

            for i in range(1, 7):
                current_value = current_value * (1 + avg_growth)
                future_forecast[f"Month+{i}"] = round(float(current_value), 2)

            # ==============================
            # TREND
            # ==============================
            trend_direction = "increasing" if avg_growth > 0 else "decreasing"

            if abs(avg_growth) < 0.02:
                confidence = "Low"
            elif abs(avg_growth) < 0.05:
                confidence = "Medium"
            else:
                confidence = "High"

            next_month = list(future_forecast.values())[0]

            lower = next_month * 0.95
            upper = next_month * 1.05

            if avg_growth > 0.05:
                trend_strength = "Strong Growth"
            elif avg_growth > 0:
                trend_strength = "Moderate Growth"
            elif avg_growth > -0.05:
                trend_strength = "Moderate Decline"
            else:
                trend_strength = "Strong Decline"

            if avg_growth < 0:
                risk = "Declining Demand ⚠️"
            else:
                risk = "Stable Demand ✅"

            top_months = monthly_sales.sort_values(ascending=False).head(3).index.tolist()

            # ==============================
            # METRICS
            # ==============================
            metrics = {
                "total_sales": round(int(df["units_sold"].sum()), 2),
                "avg_sales": round(float(df["units_sold"].mean()), 2),
                "next_month_forecast": round(float(list(future_forecast.values())[0]), 2),
                "forecast_range": f"{round(lower)} - {round(upper)}",
                "growth_display": f"{round(avg_growth * 100, 2)}% ({'Increasing 📈' if avg_growth > 0 else 'Decreasing 📉'})",
                "trend": trend_direction,
                "trend_strength": trend_strength,
                "forecast_confidence": confidence,
                "risk_indicator": risk,
                "best_month": best_month_name,
                "worst_month": worst_month_name,
            }
            

            # ==============================
            # INSIGHTS
            # ==============================
            insights = [
                f"Sales are showing a {trend_direction} trend over time.",
                f"Average monthly growth is {round(avg_growth * 100, 2)}%.",
                f"Highest sales recorded in {best_month_name}.",
                f"Lowest performance observed in {worst_month_name}.",
                f"Peak sales months are {', '.join(map(str, top_months))}.",
                f"Forecast confidence is {confidence}, indicating prediction reliability.",
                "Forecast is based on past sales trends and assumes similar future conditions."
            ]

            # ==============================
            # RECOMMENDATIONS
            # ==============================
            recommendations = [
                "Adjust inventory based on upcoming demand forecast.",
                "Focus marketing efforts during high-performing months.",
                "Investigate causes behind low-performing periods.",
                "Prepare for demand fluctuations using forecast trends."
            ]

            # ==============================
            # RETURN
            # ==============================
            return {
                "metrics": metrics,
                "insights": insights,
                "recommendations": recommendations,
                "monthly_sales": monthly_sales.to_dict(),
                "forecast": future_forecast,
                "processed_path": processed_path
            }
        
        # ==============================
        # MODE-BASED LOGIC
        # ==============================

        

        elif operation == "business_analysis":
            # ==============================
            # APPLY USER FILTERS
            # ==============================

            if category != "all":
                df = df[df["category"] == category]

            if region != "all":
                df = df[df["region"] == region]

            if year != "all" and "year" in df.columns:
                df = df[df["year"] == int(year)]

            # ==============================
            # CREATE REVENUE
            # ==============================

            if "price" in df.columns:
                df["revenue"] = df["units_sold"] * df["price"]
            else:
                df["revenue"] = df["units_sold"]

            logger.info("Running Business Analysis Mode")

            logger.info("STEP 1: Starting aggregations")

            total_sales = df["units_sold"].sum()
            logger.info(f"STEP 2: total_sales = {total_sales}")

            avg_sales = df["units_sold"].mean()
            logger.info(f"STEP 3: avg_sales = {avg_sales}")

            category_sales = df.groupby("category")["units_sold"].sum()
            logger.info("STEP 4: category_sales computed")

            region_sales = df.groupby("region")["units_sold"].sum()
            logger.info("STEP 5: region_sales computed")

            

            # ==============================
            # BASIC AGGREGATIONS
            # ==============================

            total_rows = len(df)

            total_sales = df["units_sold"].sum()
            avg_sales = df["units_sold"].mean()

            # Category-wise sales
            category_sales = df.groupby("category")["units_sold"].sum().sort_values(ascending=False)

            # Region-wise sales
            region_sales = df.groupby("region")["units_sold"].sum().sort_values(ascending=False)

            # ==============================
            # MONTHLY SALES (FOR DASHBOARD)
            # ==============================
            if "date" in df.columns:
                df["month"] = pd.to_datetime(df["date"]).dt.month
                monthly_sales = df.groupby("month")["units_sold"].sum().to_dict()
            else:
                monthly_sales = {}

            # ==============================
            # TOP / LOW PERFORMERS
            # ==============================

            top_category = category_sales.idxmax() if not category_sales.empty else "N/A"
            lowest_category = category_sales.idxmin() if not category_sales.empty else "N/A"

            top_region = region_sales.idxmax() if not region_sales.empty else "N/A"
            lowest_region = region_sales.idxmin() if not region_sales.empty else "N/A"

            # ==============================
            # CONTRIBUTION %
            # ==============================

            if total_sales == 0:
                category_share = category_sales * 0
                region_share = region_sales * 0
            else:
                category_share = ((category_sales / total_sales) * 100).round(2)
                region_share = ((region_sales / total_sales) * 100).round(2)

            category_share = category_share.to_dict()
            region_share = region_share.to_dict()

            # ==============================
            # TOP / BOTTOM 3
            # ==============================

            top_3_categories = category_sales.head(3).to_dict()
            bottom_3_categories = category_sales.tail(3).to_dict()

            # ==============================
            # PERFORMANCE GAP
            # ==============================

            if not category_sales.empty:
                performance_gap = category_sales.max() - category_sales.min()
            else:
                performance_gap = 0

            if performance_gap > 50000:
                business_health = "Unbalanced ⚠️"
            else:
                business_health = "Stable ✅"

            # ==============================
            # REGION RANKING
            # ==============================

            region_ranking = region_sales.sort_values(ascending=False).to_dict()

            # ==============================
            # DUAL METRICS
            # ==============================

            total_units = df["units_sold"].sum()
            avg_units = df["units_sold"].mean()

            total_revenue = df["revenue"].sum()
            avg_revenue = df["revenue"].mean()

            # ==============================
            # METRICS
            # ==============================

            metrics = {
                "total_sales": round(int(total_sales), 2),
                "avg_sales": round(float(avg_sales), 2),
                "top_category": str(top_category),
                "top_region": str(top_region),
                "category_count": int(df["category"].nunique()),
                "region_count": int(df["region"].nunique()),
                "performance_gap": float(performance_gap),
                "business_health": business_health
            }

            # ==============================
            # INSIGHTS (ADVANCED)
            # ==============================

            insights = [
                f"{top_category} contributes {category_share.get(top_category, 0)}% of total sales.",
                f"{lowest_category} is underperforming with only {category_share.get(lowest_category, 0)}% share.",
                f"{top_region} region dominates with {region_share.get(top_region, 0)}% of total sales.",
                f"{lowest_region} region has the lowest contribution at {region_share.get(lowest_region, 0)}%.",
                f"There is a performance gap of {int(performance_gap)} units between top and lowest category.",
                "Sales distribution varies significantly across categories and regions."
            ]
            if category_share.get(top_category, 0) > 40:
                insights.append(f"{top_category} dominates heavily → business dependency risk.")

            if category_share.get(lowest_category, 0) < 10:
                insights.append(f"{lowest_category} has very low contribution → consider restructuring.")

            # ==============================
            # RECOMMENDATIONS (SMART)
            # ==============================

            recommendations = [
                f"Increase investment in {top_category} to maximize returns.",
                f"Improve strategy for {lowest_category} category to boost performance.",
                f"Expand operations in {top_region} region.",
                f"Investigate low demand in {lowest_region} region.",
                "Optimize inventory allocation based on category and region demand.",
                "Focus marketing efforts on high-performing segments."
            ]

            # ==============================
            # RETURN FINAL OUTPUT
            # ==============================
            return {
                "units_metrics": {
                    "total_units": int(total_units),
                    "avg_units": round(float(avg_units), 2)
                },
                "revenue_metrics": {
                    "total_revenue": round(float(total_revenue), 2),
                    "avg_revenue": round(float(avg_revenue), 2)
                },

                "category_list": sorted(df["category"].dropna().unique().tolist()),
                "region_list": sorted(df["region"].dropna().unique().tolist()),
                "year_list": sorted(df["year"].dropna().unique().tolist()) if "year" in df.columns else [],

                # keep your old outputs also
                "metrics": metrics,
                "insights": insights,
                "recommendations": recommendations,
                "category_sales": category_sales.to_dict(),
                "region_sales": region_sales.to_dict(),
                "category_share": category_share,
                "region_share": region_share,
                "top_categories": top_3_categories,
                "low_categories": bottom_3_categories,
                "region_ranking": region_ranking,
                "monthly_sales": monthly_sales,
                "processed_path": processed_path
            }
        

        else:
            raise ValueError(f"Unsupported operation: {operation}")



    except Exception as e:
        logger.error(f"RUN_ID={run_id} | Pipeline failed: {str(e)}")
        raise


