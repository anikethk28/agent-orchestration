from orchestration.config import get_settings
from orchestration.graph.state import SpecialistType
from .base_specialist import BaseSpecialist


class WriterAgent(BaseSpecialist):
    name = "writer"
    specialist_type = SpecialistType.WRITER
    domain_description = (
        "You specialize in content creation, summarization, and formatting. "
        "Produce polished, well-structured written content. "
        "Use file_write to save deliverables when needed."
    )

    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(model=settings.specialist_model)
