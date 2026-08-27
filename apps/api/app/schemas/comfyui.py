from typing import Literal

from pydantic import BaseModel


class ComfyUIHealthRead(BaseModel):
    status: Literal["online", "offline"]
