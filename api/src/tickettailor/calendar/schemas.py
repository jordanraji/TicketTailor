from pydantic import BaseModel, ConfigDict


class CalendarTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token: str
    feed_url: str
