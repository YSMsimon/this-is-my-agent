from pydantic import BaseModel

class Response(BaseModel):
    content: str
    tool_calls: list[dict] = []
    reasoning: str = ''
    model: str = ''
    finish_reason: str = ''
    input_tokens: int = 0
    output_tokens: int = 0