from typing import Optional
from pydantic import BaseModel


class CommentRequest(BaseModel):
    comment: str


class StatusChangeRequest(BaseModel):
    status: str
