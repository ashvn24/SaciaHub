"""Document/Folder management schemas."""

from typing import Optional

from pydantic import BaseModel


class FolderSchema(BaseModel):
    Company_Portal_Url: Optional[str] = None
    FolderName: str
    EntityType: str
    ParentFolderID: Optional[int] = None


class FileSchema(BaseModel):
    Company_Portal_Url: Optional[str] = None
    FolderID: int
    FileName: str
    FileContent: str
    ContentType: str


class UploadSchema(BaseModel):
    Company_Portal_Url: str
    User_Id: str
