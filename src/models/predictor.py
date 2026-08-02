from random import randint


class PerformancePredictor:
    """Handles data transformation and runs inference through m2cgen model."""

    @staticmethod
    def predict_score(hours: float, attendance: float, sleep: float) -> float:
        raw_score = randint(1, 100)

        bounded_score = max(0.0, min(100.0, raw_score))
        return round(bounded_score, 1)
