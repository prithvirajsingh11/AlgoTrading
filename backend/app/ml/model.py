"""ML model abstractions (reserved for ML phase)."""


class MLTradingModel:
    """Wrapper class for scikit-learn / XGBoost models.

    ponytail: To be implemented in the ML enhancement phase.
    """

    def __init__(self, model_type: str = "xgboost"):
        self.model_type = model_type
        raise NotImplementedError("ML models reserved for ML phase.")
