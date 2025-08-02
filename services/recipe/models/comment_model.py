"""
레시피 후기(코멘트) 테이블 ORM 모델 (변수는 소문자, DB 컬럼명은 대문자)
"""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Comment(Base):
    __tablename__ = "COMMENT"
    comment_id = Column("COMMENT_ID", Integer, primary_key=True, autoincrement=True)
    recipe_id = Column("RECIPE_ID", Integer, ForeignKey("FCT_RECIPE.RECIPE_ID"), nullable=False)
    user_id = Column("USER_ID", Integer, nullable=False)
    comment = Column("COMMENT", String(1000), nullable=False)
