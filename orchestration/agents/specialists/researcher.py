from orchestration.config import get_settings
from orchestration.graph.state import SpecialistType
from .base_specialist import BaseSpecialist


class ResearcherAgent(BaseSpecialist):
    name = "researcher"
    specialist_type = SpecialistType.RESEARCHER
    domain_description = (
        "You specialize in information gathering and research. "
        "Use web_search to find relevant sources, then synthesize findings into clear, cited summaries."
    )

    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(model=settings.specialist_model)
