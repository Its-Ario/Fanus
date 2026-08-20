# DEV ONLY
import itertools
import os
import time
from pathlib import Path

import m2cgen as m2c
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import KFold

from train import load_and_harmonize_datasets


def benchmark_combination(df, max_depth, n_estimators, learning_rate):
    conditions = [
        (df["AcademicGrade"] < 10.0) | (df["Absences"] >= 12) | (df["PastFailures"] >= 2),
        (df["AcademicGrade"] < 14.0) | (df["Absences"] >= 6) | (df["PastFailures"] == 1),
    ]
    df["RiskScore"] = np.select(conditions, [2.0, 1.0], default=0.0)

    feature_cols = ["DailyStudyHours", "Absences", "AcademicGrade", "PastFailures", "SupportLevel"]
    X = df[feature_cols]
    y = df["RiskScore"]

    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    maes, mses = [], []

    for train_idx, test_idx in kf.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            base_score=0.5,
            random_state=42,
        )
        model.fit(X_train, y_train)

        preds = model.predict(X_test)
        maes.append(mean_absolute_error(y_test, preds))
        mses.append(mean_squared_error(y_test, preds))

    avg_mae = np.mean(maes)
    avg_rmse = np.sqrt(np.mean(mses))

    full_model = xgb.XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        base_score=0.5,
        random_state=42,
    )
    full_model.fit(X, y)

    code = m2c.export_to_python(full_model)
    temp_file = Path("temp_model.py")
    with open(temp_file, "w") as f:
        f.write(code)

    file_size_kb = temp_file.stat().st_size / 1024.0

    import temp_model  # type: ignore

    sample_input = [3.5, 2.0, 16.5, 0.0, 3.0]

    start_time = time.perf_counter_ns()
    for _ in range(1000):
        _ = temp_model.score(sample_input)
    end_time = time.perf_counter_ns()

    avg_latency_us = ((end_time - start_time) / 1000.0) / 1000.0

    if temp_file.exists():
        os.remove(temp_file)

    return {
        "max_depth": max_depth,
        "n_estimators": n_estimators,
        "learning_rate": learning_rate,
        "MAE": round(avg_mae, 4),
        "RMSE": round(avg_rmse, 4),
        "File_Size_KB": round(file_size_kb, 1),
        "Latency_us": round(avg_latency_us, 2),
    }


def main():
    print("Loading dataset...")
    df = load_and_harmonize_datasets()

    depths = [2, 3, 4, 5]
    estimators = [15, 25, 40, 50, 60, 100]
    learning_rates = [0.25, 0.3, 0.35]

    results = []
    print("\nRunning...\n")

    for d, n, lr in itertools.product(depths, estimators, learning_rates):
        res = benchmark_combination(df, d, n, lr)
        results.append(res)
        print(
            f"Depth: {d} | Trees: {n:2d} | LR: {lr:.2f}, MAE: {res['MAE']} | Size: {res['File_Size_KB']:5.1f} KB | Latency: {res['Latency_us']} µs"
        )

    res_df = pd.DataFrame(results).sort_values(by="MAE")
    print("\n================ TOP 5 ================")
    print(res_df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
