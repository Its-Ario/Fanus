from src.models.predictor import RiskPredictor

level, percentage = RiskPredictor.predict_student_risk(
    daily_hours=0, absences=1, gpa=15.0, past_failures=1, support_level=2
)

print(level, percentage)
