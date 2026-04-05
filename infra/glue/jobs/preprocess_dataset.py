import json
import sys
from datetime import datetime, timezone

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DateType,
    DoubleType,
    FloatType,
    IntegerType,
    LongType,
    ShortType,
    TimestampType,
)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _get_arg_with_default(name: str, default: str) -> str:
    for token in sys.argv:
        if token.startswith(f"--{name}="):
            return token.split("=", 1)[1]
    return default


args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "job_id",
        "input_bucket",
        "input_key",
        "processed_bucket",
        "processed_prefix",
        "feature_bucket",
        "feature_prefix",
        "summary_bucket",
        "summary_prefix",
    ],
)

apply_pca = _get_arg_with_default("apply_pca", "false").strip().lower() in {"true", "1", "yes"}

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

job_id = args["job_id"]
input_s3_uri = f"s3://{args['input_bucket']}/{args['input_key']}"
cleaned_output_s3_uri = f"s3://{args['processed_bucket']}/{args['processed_prefix'].strip('/')}/{job_id}/cleaned/"
feature_output_s3_uri = f"s3://{args['feature_bucket']}/{args['feature_prefix'].strip('/')}/{job_id}/train/"
summary_key = f"{args['summary_prefix'].strip('/')}/{job_id}.json"

target_keywords = {"target", "label", "price", "sales", "output", "y", "revenue", "demand", "churn"}


def _read_dataset(path: str) -> DataFrame:
    if path.lower().endswith(".parquet"):
        return spark.read.parquet(path)
    return spark.read.option("header", True).option("inferSchema", True).csv(path)


def _numeric_columns(df: DataFrame) -> list[str]:
    numeric_types = (IntegerType, LongType, FloatType, DoubleType, ShortType)
    return [f.name for f in df.schema.fields if isinstance(f.dataType, numeric_types)]


def _datetime_columns(df: DataFrame) -> list[str]:
    dt_types = (TimestampType, DateType)
    dt_cols = [f.name for f in df.schema.fields if isinstance(f.dataType, dt_types)]
    for col_name in df.columns:
        lowered = col_name.lower()
        if lowered.endswith("_date") or lowered.endswith("_time") or "date" in lowered:
            if col_name not in dt_cols:
                dt_cols.append(col_name)
    return dt_cols


def _fill_missing(df: DataFrame) -> DataFrame:
    numeric_cols = _numeric_columns(df)
    fill_map = {}
    for col_name in numeric_cols:
        med = df.approxQuantile(col_name, [0.5], 0.01)
        fill_map[col_name] = med[0] if med else 0
    if fill_map:
        df = df.fillna(fill_map)

    for col_name in df.columns:
        if col_name in numeric_cols:
            continue
        top = (
            df.groupBy(col_name)
            .count()
            .orderBy(F.desc("count"))
            .select(col_name)
            .limit(1)
            .collect()
        )
        fallback = str(top[0][0]) if top and top[0][0] is not None else "unknown"
        df = df.fillna({col_name: fallback})
    return df


def _clip_outliers_iqr(df: DataFrame) -> DataFrame:
    numeric_cols = _numeric_columns(df)
    for col_name in numeric_cols:
        q1, q3 = df.approxQuantile(col_name, [0.25, 0.75], 0.01)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        df = df.withColumn(
            col_name,
            F.when(F.col(col_name) < lower, F.lit(lower))
            .when(F.col(col_name) > upper, F.lit(upper))
            .otherwise(F.col(col_name)),
        )
    return df


def _expand_datetime_features(df: DataFrame) -> DataFrame:
    dt_cols = _datetime_columns(df)
    for col_name in dt_cols:
        ts_col = F.to_timestamp(F.col(col_name))
        df = df.withColumn(f"{col_name}_year", F.year(ts_col))
        df = df.withColumn(f"{col_name}_month", F.month(ts_col))
        df = df.withColumn(f"{col_name}_day", F.dayofmonth(ts_col))
    return df


def _schema_summary(df: DataFrame) -> list[dict]:
    total_rows = max(df.count(), 1)
    summary = []
    numeric_cols = set(_numeric_columns(df))
    for field in df.schema.fields:
        col_name = field.name
        null_count = df.filter(F.col(col_name).isNull()).count()
        unique_count = df.select(F.approx_count_distinct(F.col(col_name)).alias("u")).collect()[0]["u"]
        variance = None
        if col_name in numeric_cols:
            variance = (
                df.select(F.var_pop(F.col(col_name)).alias("v")).collect()[0]["v"]
                if total_rows > 1
                else 0
            )
        summary.append(
            {
                "name": col_name,
                "dtype": str(field.dataType),
                "null_count": int(null_count),
                "null_pct": round((null_count / total_rows) * 100, 3),
                "unique_count": int(unique_count or 0),
                "variance": float(variance) if variance is not None else None,
            }
        )
    return summary


def _target_candidates(schema_rows: list[dict]) -> list[str]:
    candidates = []
    for col in schema_rows:
        name = col["name"]
        lowered = name.lower()
        if any(keyword in lowered for keyword in target_keywords):
            candidates.append(name)
    if candidates:
        return candidates

    numeric = [col for col in schema_rows if "int" in col["dtype"] or "double" in col["dtype"] or "float" in col["dtype"]]
    numeric.sort(key=lambda item: (item.get("variance") or 0), reverse=True)
    return [col["name"] for col in numeric[:3]]


def _write_summary(payload: dict):
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=args["summary_bucket"],
        Key=summary_key,
        Body=json.dumps(payload, default=str).encode("utf-8"),
        ContentType="application/json",
    )


raw_df = _read_dataset(input_s3_uri)
raw_count = raw_df.count()
dedup_df = raw_df.dropDuplicates()
dedup_count = dedup_df.count()

clean_df = _fill_missing(dedup_df)
clean_df = _clip_outliers_iqr(clean_df)
feature_df = _expand_datetime_features(clean_df)

# Placeholder: PCA can be added here when a strict dimensionality reduction contract is required.
pca_applied = bool(apply_pca and False)

clean_df.write.mode("overwrite").parquet(cleaned_output_s3_uri)
feature_df.coalesce(1).write.mode("overwrite").option("header", True).csv(feature_output_s3_uri)

schema_rows = _schema_summary(feature_df)
summary_payload = {
    "job_id": job_id,
    "generated_at": _now_iso(),
    "input_s3_uri": input_s3_uri,
    "cleaned_data_s3_uri": cleaned_output_s3_uri,
    "feature_data_s3_uri": feature_output_s3_uri,
    "raw_row_count": int(raw_count),
    "deduplicated_row_count": int(dedup_count),
    "final_row_count": int(feature_df.count()),
    "column_count": len(feature_df.columns),
    "pca_applied": pca_applied,
    "schema_summary": {"columns": schema_rows},
    "target_column_candidates": _target_candidates(schema_rows),
}
_write_summary(summary_payload)

job.commit()
