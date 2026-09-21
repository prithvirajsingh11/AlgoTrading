"""Structured dataset validation service for algorithmic research datasets.

Produces detailed, non-throwing validation reports containing errors, warnings,
and statistical integrity summaries.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np


@dataclass
class ValidationReport:
    """Structured report returned by DatasetValidator."""

    valid: bool
    rows: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "rows": self.rows,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": self.summary,
        }


class DatasetValidator:
    """Non-throwing validation service for OHLCV datasets."""

    REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

    @classmethod
    def validate(
        cls,
        df: pd.DataFrame,
        min_bars: int = 10,
        extreme_jump_threshold: float = 0.50,
    ) -> ValidationReport:
        """Evaluates DataFrame against quantitative integrity rules."""
        errors: List[str] = []
        warnings: List[str] = []
        summary: Dict[str, Any] = {
            "min_bars_required": min_bars,
            "extreme_jump_threshold": extreme_jump_threshold,
        }

        # 1. Null / Empty checks
        if df is None or df.empty:
            errors.append("Dataset is empty or null.")
            return ValidationReport(valid=False, rows=0, errors=errors, warnings=warnings, summary=summary)

        total_rows = len(df)
        summary["total_rows"] = total_rows

        # 2. Required columns check
        missing_cols = [c for c in cls.REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")
            return ValidationReport(valid=False, rows=total_rows, errors=errors, warnings=warnings, summary=summary)

        # Work on a copy for type casting and validation
        df_eval = df.copy()

        # 3. Missing / NaN values
        nan_counts = df_eval[cls.REQUIRED_COLUMNS].isna().sum().to_dict()
        total_nans = sum(nan_counts.values())
        summary["nan_counts"] = nan_counts
        if total_nans > 0:
            errors.append(f"Found {total_nans} NaN or null values across required columns: {nan_counts}")

        # 4. Timestamp format, duplicates, and ordering
        try:
            df_eval["timestamp"] = pd.to_datetime(df_eval["timestamp"])
        except Exception as e:
            errors.append(f"Timestamp column could not be converted to datetime: {str(e)}")
            return ValidationReport(valid=False, rows=total_rows, errors=errors, warnings=warnings, summary=summary)

        dup_count = int(df_eval["timestamp"].duplicated().sum())
        summary["duplicate_timestamps"] = dup_count
        if dup_count > 0:
            errors.append(f"Found {dup_count} duplicate timestamps.")

        is_sorted = bool(df_eval["timestamp"].is_monotonic_increasing)
        summary["is_chronologically_sorted"] = is_sorted
        if not is_sorted:
            errors.append("Timestamps are not strictly in chronological ascending order.")

        # 5. Non-positive prices and negative volume
        for col in ["open", "high", "low", "close"]:
            non_pos = int((df_eval[col] <= 0).sum())
            if non_pos > 0:
                errors.append(f"Column '{col}' has {non_pos} non-positive (<= 0) price values.")

        neg_vol = int((df_eval["volume"] < 0).sum())
        summary["negative_volume_count"] = neg_vol
        if neg_vol > 0:
            errors.append(f"Column 'volume' has {neg_vol} negative (< 0) volume values.")

        # 6. Invalid OHLC relationships
        # High must be >= Low, Open, Close
        # Low must be <= High, Open, Close
        high_lt_low = int((df_eval["high"] < df_eval["low"]).sum())
        high_lt_open = int((df_eval["high"] < df_eval["open"]).sum())
        high_lt_close = int((df_eval["high"] < df_eval["close"]).sum())
        low_gt_open = int((df_eval["low"] > df_eval["open"]).sum())
        low_gt_close = int((df_eval["low"] > df_eval["close"]).sum())

        summary["ohlc_violations"] = {
            "high_less_than_low": high_lt_low,
            "high_less_than_open": high_lt_open,
            "high_less_than_close": high_lt_close,
            "low_greater_than_open": low_gt_open,
            "low_greater_than_close": low_gt_close,
        }

        if high_lt_low > 0:
            errors.append(f"High < Low violation detected in {high_lt_low} rows.")
        if high_lt_open > 0:
            errors.append(f"High < Open violation detected in {high_lt_open} rows.")
        if high_lt_close > 0:
            errors.append(f"High < Close violation detected in {high_lt_close} rows.")
        if low_gt_open > 0:
            errors.append(f"Low > Open violation detected in {low_gt_open} rows.")
        if low_gt_close > 0:
            errors.append(f"Low > Close violation detected in {low_gt_close} rows.")

        # 7. Insufficient observations
        if total_rows < min_bars:
            errors.append(f"Insufficient observations: dataset has {total_rows} rows, minimum required is {min_bars}.")

        # 8. Time gaps & Suspicious extreme jumps (Warnings)
        if total_rows > 1 and is_sorted:
            # Check price jump warning
            pct_change = df_eval["close"].pct_change().abs()
            extreme_jumps = int((pct_change >= extreme_jump_threshold).sum())
            summary["extreme_jumps_count"] = extreme_jumps
            if extreme_jumps > 0:
                max_jump = float(pct_change.max())
                warnings.append(
                    f"Detected {extreme_jumps} suspicious price jumps >= {extreme_jump_threshold:.0%} "
                    f"(maximum single-bar jump: {max_jump:.1%})."
                )

            # Check timestamp gaps (large gaps between consecutive timestamps)
            diffs = df_eval["timestamp"].diff().dropna()
            median_diff = diffs.median()
            large_gaps = int((diffs > (median_diff * 4)).sum()) if pd.notna(median_diff) else 0
            summary["large_timestamp_gaps"] = large_gaps
            if large_gaps > 0:
                warnings.append(f"Detected {large_gaps} timestamp gaps greater than 4x the median bar interval.")

        if not df_eval.empty and "timestamp" in df_eval.columns:
            summary["start_timestamp"] = df_eval["timestamp"].min().isoformat()
            summary["end_timestamp"] = df_eval["timestamp"].max().isoformat()

        is_valid = len(errors) == 0
        return ValidationReport(
            valid=is_valid,
            rows=total_rows,
            errors=errors,
            warnings=warnings,
            summary=summary,
        )
