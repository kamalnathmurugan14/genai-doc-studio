"""Wires services together."""

from app.config import Settings
from app.db.session import init_db
from app.llm.client import LLM, OllamaClient
from app.services.engine import Engine
from app.services.prompt_store import PromptStore
from app.services.run_store import RunStore


class Container:
    def __init__(self, settings: Settings, llm: LLM | None = None) -> None:
        self.settings = settings
        settings.docs_root.mkdir(parents=True, exist_ok=True)
        init_db(settings.db_path)
        self.llm: LLM = llm or OllamaClient(settings)
        self.prompts = PromptStore(settings)
        self.runs = RunStore(settings)
        self.engine = Engine(settings, self.llm, self.prompts, self.runs)
