"""Pydantic schemas for structured extraction. Every value carries an `evidence` quote we can verify."""

from pydantic import BaseModel


class Item(BaseModel):
    value: str
    evidence: str


class Entities(BaseModel):
    dates: list[Item] = []
    people: list[Item] = []
    amounts: list[Item] = []
    action_items: list[Item] = []


class InvoiceInfo(BaseModel):
    invoice_number: Item | None = None
    vendor: Item | None = None
    customer: Item | None = None
    invoice_date: Item | None = None
    due_date: Item | None = None
    total_amount: Item | None = None
    line_items: list[Item] = []


class ContractInfo(BaseModel):
    parties: list[Item] = []
    effective_date: Item | None = None
    end_or_renewal_date: Item | None = None
    termination_notice: Item | None = None
    governing_law: Item | None = None
    key_obligations: list[Item] = []


class MeetingNotes(BaseModel):
    date: Item | None = None
    attendees: list[Item] = []
    decisions: list[Item] = []
    action_items: list[Item] = []


SCHEMAS: dict[str, type[BaseModel]] = {
    "entities": Entities,
    "invoice": InvoiceInfo,
    "contract": ContractInfo,
    "meeting": MeetingNotes,
}

_EX = '{"value": "...", "evidence": "exact quote from the document"}'
EXAMPLES: dict[str, str] = {
    "entities": f'{{"dates": [{_EX}], "people": [{_EX}], "amounts": [{_EX}], "action_items": [{_EX}]}}',
    "invoice": f'{{"invoice_number": {_EX}, "vendor": {_EX}, "customer": {_EX}, "invoice_date": {_EX}, "due_date": {_EX}, "total_amount": {_EX}, "line_items": [{_EX}]}}',
    "contract": f'{{"parties": [{_EX}], "effective_date": {_EX}, "end_or_renewal_date": {_EX}, "termination_notice": {_EX}, "governing_law": {_EX}, "key_obligations": [{_EX}]}}',
    "meeting": f'{{"date": {_EX}, "attendees": [{_EX}], "decisions": [{_EX}], "action_items": [{_EX}]}}',
}
