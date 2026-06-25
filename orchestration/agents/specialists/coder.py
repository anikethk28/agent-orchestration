from orchestration.config import get_settings
from orchestration.graph.state import SpecialistType
from .base_specialist import BaseSpecialist


class CoderAgent(BaseSpecialist):
    name = "coder"
    specialist_type = SpecialistType.CODER
    domain_description = (
        "You specialize in Python programming, algorithmic problem solving, and data transformation. "
        "Use execute_python to run code iteratively until it produces correct output. "
        "Use file_read/file_write for file-based tasks."
    )

    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(model=settings.specialist_model)
