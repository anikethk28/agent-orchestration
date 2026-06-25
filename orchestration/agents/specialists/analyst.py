from orchestration.config import get_settings
from orchestration.graph.state import SpecialistType
from .base_specialist import BaseSpecialist


class AnalystAgent(BaseSpecialist):
    name = "analyst"
    specialist_type = SpecialistType.ANALYST
    domain_description = (
        "You specialize in data analysis, pattern recognition, and structured extraction. "
        "Use execute_python for numerical work, database_query for structured data, "
        "and web_search when you need supporting data. Produce structured, quantified insights."
    )

    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(model=settings.specialist_model)
