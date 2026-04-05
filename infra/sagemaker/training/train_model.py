from __future__ import annotations

import argparse
import json
import os
import pathlib
from dataclasses import dataclass
from typing import Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier


@dataclass
class TrainingConfig:
    task_type: str
    algorithm: str
    target_column: str
    time_column: str
    test_size: float
    random_state: int
    model_dir: str
    train_dir: str


def parse_args() -> TrainingConfig:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_type", type=str, default="regression")
    parser.add_argument("--algorithm", type=str, default="linear_regression")
    parser.add_argument("--target_column", type=str, default="")
    parser.add_argument("--time_column", type=str, default="")
    parser.add_argument("--test_size", type=float, default=0.2)
    parser.add_argument("--random_state", type=int, default=42)
    parser.add_argument("--model_dir", type=str, default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    parser.add_argument(
        "--train_dir",
        type=str,
        default=os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"),
    )
    args, _ = parser.parse_known_args()
    return TrainingConfig(
        task_type=args.task_type.strip().lower(),
        algorithm=args.algorithm.strip().lower(),
        target_column=args.target_column.strip(),
        time_column=args.time_column.strip(),
        test_size=float(args.test_size),
        random_state=int(args.random_state),
        model_dir=args.model_dir,
        train_dir=args.train_dir,
    )


def _find_csv(train_dir: str) -> str:
    directory = pathlib.Path(train_dir)
    candidates = sorted(directory.rglob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No CSV file found under {train_dir}")
    return str(candidates[0])


def _pick_target(df: pd.DataFrame, configured_target: str) -> str:
    if configured_target and configured_target in df.columns:
        return configured_target

    keywords = ["target", "label", "price", "sales", "output", "y", "revenue", "demand", "churn", "class"]
    for col in df.columns:
        lowered = col.lower()
        if any(keyword in lowered for keyword in keywords):
            return col
    return df.columns[-1]


def _build_preprocessor(x: pd.DataFrame) -> ColumnTransformer:
    numeric_cols = x.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [col for col in x.columns if col not in numeric_cols]

    numeric_transformer = Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))])
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_cols),
            ("cat", categorical_transformer, categorical_cols),
        ],
        remainder="drop",
    )


def _regression_model(algorithm: str):
    if algorithm == "random_forest":
        return RandomForestRegressor(n_estimators=250, random_state=42, n_jobs=-1)
    return LinearRegression()


def _classification_model(algorithm: str):
    if algorithm == "decision_tree":
        return DecisionTreeClassifier(max_depth=12, random_state=42)
    return RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)


def _forecast_features(df: pd.DataFrame, target_column: str, time_column: str) -> pd.DataFrame:
    work = df.copy()
    if time_column and time_column in work.columns:
        work[time_column] = pd.to_datetime(work[time_column], errors="coerce")
        work = work.dropna(subset=[time_column]).sort_values(time_column)
        work["time_index"] = np.arange(len(work))
    else:
        work["time_index"] = np.arange(len(work))

    work["lag_1"] = work[target_column].shift(1)
    work["lag_2"] = work[target_column].shift(2)
    work["lag_3"] = work[target_column].shift(3)
    work = work.dropna().reset_index(drop=True)
    return work


def _train_regression(
    df: pd.DataFrame,
    target_column: str,
    algorithm: str,
    test_size: float,
    random_state: int,
) -> Tuple[Pipeline, dict]:
    x = df.drop(columns=[target_column])
    y = df[target_column]
    preprocessor = _build_preprocessor(x)
    model = _regression_model(algorithm)

    pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=random_state,
    )
    pipeline.fit(x_train, y_train)
    preds = pipeline.predict(x_test)
    metrics = {
        "rmse": float(np.sqrt(mean_squared_error(y_test, preds))),
        "mae": float(mean_absolute_error(y_test, preds)),
        "r2": float(r2_score(y_test, preds)),
    }
    return pipeline, metrics


def _train_classification(
    df: pd.DataFrame,
    target_column: str,
    algorithm: str,
    test_size: float,
    random_state: int,
) -> Tuple[Pipeline, dict]:
    x = df.drop(columns=[target_column])
    y = df[target_column]
    preprocessor = _build_preprocessor(x)
    model = _classification_model(algorithm)

    pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y if y.nunique() > 1 else None,
    )
    pipeline.fit(x_train, y_train)
    preds = pipeline.predict(x_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, preds)),
        "precision_weighted": float(precision_score(y_test, preds, average="weighted", zero_division=0)),
        "recall_weighted": float(recall_score(y_test, preds, average="weighted", zero_division=0)),
        "f1_weighted": float(f1_score(y_test, preds, average="weighted", zero_division=0)),
    }
    return pipeline, metrics


def _train_forecasting(
    df: pd.DataFrame,
    target_column: str,
    time_column: str,
    test_size: float,
) -> Tuple[Pipeline, dict]:
    prepared = _forecast_features(df=df, target_column=target_column, time_column=time_column)
    x = prepared[["time_index", "lag_1", "lag_2", "lag_3"]]
    y = prepared[target_column]

    split_index = int((1 - test_size) * len(prepared))
    split_index = max(split_index, 5)
    x_train, x_test = x.iloc[:split_index], x.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

    model = LinearRegression()
    model.fit(x_train, y_train)
    preds = model.predict(x_test)

    mape = float(np.mean(np.abs((y_test - preds) / np.where(np.abs(y_test) < 1e-9, 1.0, np.abs(y_test)))) * 100)
    metrics = {
        "rmse": float(np.sqrt(mean_squared_error(y_test, preds))),
        "mae": float(mean_absolute_error(y_test, preds)),
        "mape": mape,
    }
    pipeline = Pipeline(steps=[("model", model)])
    return pipeline, metrics


def main():
    cfg = parse_args()
    dataset_path = _find_csv(cfg.train_dir)
    df = pd.read_csv(dataset_path)
    if df.empty:
        raise ValueError("Training dataset is empty.")

    target_column = _pick_target(df=df, configured_target=cfg.target_column)
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' does not exist.")

    if cfg.task_type == "classification":
        model_pipeline, metrics = _train_classification(
            df=df,
            target_column=target_column,
            algorithm=cfg.algorithm,
            test_size=cfg.test_size,
            random_state=cfg.random_state,
        )
    elif cfg.task_type == "forecasting":
        model_pipeline, metrics = _train_forecasting(
            df=df,
            target_column=target_column,
            time_column=cfg.time_column,
            test_size=cfg.test_size,
        )
    else:
        model_pipeline, metrics = _train_regression(
            df=df,
            target_column=target_column,
            algorithm=cfg.algorithm,
            test_size=cfg.test_size,
            random_state=cfg.random_state,
        )

    os.makedirs(cfg.model_dir, exist_ok=True)
    joblib.dump(model_pipeline, os.path.join(cfg.model_dir, "model.joblib"))
    evaluation = {
        "task_type": cfg.task_type,
        "algorithm": cfg.algorithm,
        "target_column": target_column,
        "row_count": int(len(df)),
        "metrics": metrics,
    }
    with open(os.path.join(cfg.model_dir, "evaluation.json"), "w", encoding="utf-8") as f:
        json.dump(evaluation, f)

    print(json.dumps({"status": "ok", "evaluation": evaluation}))


if __name__ == "__main__":
    main()
