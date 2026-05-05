from typing import List, Optional
from pydantic import BaseModel
from enum import Enum
import json

class PlanItemStatus(str, Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'

class PlanItem(BaseModel):
    content: str
    status: PlanItemStatus
    parent: Optional[str] = None
    
    
class ToDoManager:
    def __init__(self, max_items: int = 12):
        self.items: List[PlanItem] = []
        self.max_items = max_items
    
    def update(self, items: List[PlanItem]) -> str:
        if len(items) > self.max_items:
            raise ValueError(f"Keep the session plan shorter than {self.max_items}")
        if sum([item.status == PlanItemStatus.IN_PROGRESS for item in items]) > 1:
            raise ValueError("Only one item can be in progress at a time.")
        self.items = items
        return self.render()

    def render(self):
        lines = []
        for item in self.items:
            marker = {
                "pending"   : "[ ]",
                "in_progress": "[>]",
                "completed" : "[x]"
            }[item.status]
            line = f"{marker} {item.content}"
            if item.status == "in_progress" and item.parent:
                line += f" ({item.parent})"
            lines.append(line)
        completed = sum(1 for item in self.items if item.status == "completed")
        lines.append(f"\n({completed}/{len(self.items)}) completed")
        return "\n".join(lines)

    def to_do(self, items:List[PlanItem]) -> str:
        print("Updating to-do list...")
        try:
            if isinstance(items, str):
                items = json.loads(items)
            for idx, item in enumerate(items):
                if isinstance(item, dict):
                    items[idx] = PlanItem(**item)
            result = self.update(items)
            print(result)
            return result
        except Exception as e:
            print(f"Error updating to-do list: {e}")
            return f"Error updating to-do list: {e}"

    