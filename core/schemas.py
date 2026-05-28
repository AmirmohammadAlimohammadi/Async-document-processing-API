from sqlmodel import  Field, SQLModel , create_engine , Relationship 
from typing import List, Optional
from pydantic import EmailStr
from datetime import datetime
from sqlalchemy import text

# class User(SQLModel, table = True):
#     __tablename__ = "users"
#     id : Optional[int] = Field(primary_key=True, nullable=False)
#     email :EmailStr = Field(nullable=False, unique=True)
#     password : str = Field(nullable=False)
#     created_at : datetime = Field(nullable=False, default=text('now()'))
#     chats: List["Chat"] = Relationship(back_populates="user")

# class UserCreate(SQLModel):
#     email : EmailStr = Field(nullable=False, unique=True)
#     password : str

# class UserOut(SQLModel):
#     id: Optional[int]
#     email: EmailStr
#     model_config = {"from_attributes": True}

class Chat(SQLModel, table=True):
    __tablename__ = "chats"
    id: Optional[int] = Field(default=None, primary_key=True , nullable=False)
    # user_id: int = Field(foreign_key="users.id")
    messages : List["Message"] = Relationship(back_populates="chat", cascade_delete=True)
    # user : User = Relationship(back_populates="chats")
    created_at: datetime = Field(nullable=False, default=text('now()'))

class Message(SQLModel, table=True):
    __tablename__ = "messages"
    id: Optional[int] = Field(default=None, primary_key=True , nullable=False)
    chat_id: int = Field(foreign_key="chats.id")
    content: str = Field(nullable=False)
    sender: str = Field(nullable=False)
    created_at: datetime = Field(nullable=False, default=text('now()'))
    chat: Chat = Relationship(back_populates="messages")

