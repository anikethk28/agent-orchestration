"""Register all tools into the global registry at startup."""
from .code_exec import register_code_exec
from .database import register_database
from .file_ops import register_file_ops
from .web_search import register_web_search


def register_all_tools() -> None:
    register_web_search()
    register_file_ops()
    register_code_exec()
    register_database()
