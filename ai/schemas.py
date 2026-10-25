from typing import Literal
from pydantic import BaseModel, Field


class Fact(BaseModel):
    text: str = Field(description="Факт, прямо написанный в тексте новости")
    source: str = Field(description="Идентификатор новости, откуда взят факт")


class Consequence(BaseModel):
    type: Literal["risk", "opportunity"]
    description: str
    confidence: Literal["high", "medium", "low"]


class BankPosition(BaseModel):
    text: str = Field(description="Утверждение, которое есть в материале банка")
    source_material: str = Field(description="Название файла и дата материала")


class LLMInsight(BaseModel):
    """Схема ответа модели. Промпт должен требовать именно этот JSON."""
    what_happened: str = Field(description="Что произошло, своими словами")
    facts: list[Fact] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, description="Предположения, не факты")
    why_important: str = Field(description="Связь события с конкретной компанией")
    company_factors: list[str] = Field(default_factory=list, description="Признаки компании, повлиявшие на оценку")
    consequences: list[Consequence] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    bank_position: list[BankPosition] = Field(
        default_factory=list,
        description="Только утверждения, подтверждённые материалами банка. Иначе пусто."
    )
    ai_conclusions: list[str] = Field(default_factory=list, description="Выводы модели, отдельно от позиции банка")
    data_limitations: list[str] = Field(default_factory=list, description="Чего не хватает для вывода")


class TraceStep(BaseModel):
    step: str
    tool: str | None = None
    input_summary: str
    output_summary: str
    ok: bool


class Insight(LLMInsight):
    """Полный ответ сервиса. Поля news_id, company_id, sources, agent_trace заполняет код."""
    news_id: str
    company_id: str
    sources: list[str] = Field(default_factory=list)
    agent_trace: list[TraceStep] = Field(default_factory=list)