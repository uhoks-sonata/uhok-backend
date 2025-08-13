from pydantic import BaseModel

class StatusMasterSchema(BaseModel):
    """상태 마스터 스키마"""
    status_id: int
    status_code: str
    status_name: str
    
    class Config:
        from_attributes = True
        