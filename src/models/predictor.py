from typing import Tuple

from src.models import model_inference


class RiskPredictor:
    @staticmethod
    def predict_student_risk(
        daily_hours: float,
        absences: int,
        gpa: float,
        past_failures: int = 0,
        support_level: int = 2,
    ) -> Tuple[str, float]:
        """
        Runs instant (< 1ms) inference using exported m2cgen code.
        Returns: Tuple[risk_level_str, risk_percentage_float]
                 e.g. ("High", 85.0)
        """
        features = [
            float(daily_hours),
            float(absences),
            float(gpa),
            float(past_failures),
            float(support_level),
        ]

        raw_score = float(model_inference.score(features))

        clamped_score = max(0.0, min(2.0, raw_score))

        risk_percentage = round((clamped_score / 2.0) * 100.0, 1)

        if clamped_score >= 1.3:
            level = "High"
        elif clamped_score >= 0.6:
            level = "Medium"
        else:
            level = "Low"

        return level, risk_percentage
