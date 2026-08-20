# tests/test_predictor.py
from src.models.predictor import RiskPredictor


def test_perfect_student_prediction():
    level, percentage = RiskPredictor.predict_student_risk(
        daily_hours=4.0, absences=0, gpa=19.5, past_failures=0, support_level=3
    )
    assert level == "Low"
    assert percentage < 30.0


def test_failing_student_prediction():
    level, percentage = RiskPredictor.predict_student_risk(
        daily_hours=0.5, absences=20, gpa=5.0, past_failures=3, support_level=0
    )
    assert level == "High"
    assert percentage > 70.0


def test_burnout_candidate_prediction():
    level, percentage = RiskPredictor.predict_student_risk(
        daily_hours=1.0, absences=5, gpa=2.0, past_failures=1, support_level=1
    )
    assert level in ["High"]


def test_more_absences_increases_risk():
    _, risk_baseline = RiskPredictor.predict_student_risk(daily_hours=3.0, absences=2, gpa=15.0)
    _, risk_more_absent = RiskPredictor.predict_student_risk(daily_hours=3.0, absences=12, gpa=15.0)

    assert risk_more_absent >= risk_baseline
