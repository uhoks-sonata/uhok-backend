"""
레시피 및 재료(FCT_RECIPE, FCT_MTRL) 테이블의 ORM 모델 정의 모듈
- 기존 DB 테이블에 맞춰서 모델만 정의 (alembic migration 불필요)
"""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

# 공통 Base 클래스 (FastAPI, SQLAlchemy 2.0 호환)
Base = declarative_base()

class Recipe(Base):
    """
    FCT_RECIPE 테이블의 ORM 모델
    """
    __tablename__ = "FCT_RECIPE"

    RECIPE_ID = Column(Integer, primary_key=True, autoincrement=False)
    RECIPE_TITLE = Column(String(200), nullable=True)
    COOKING_NAME = Column(String(40), nullable=True)
    SCRAP_COUNT = Column(Integer, nullable=True)
    COOKING_CASE_NAME = Column(String(200), nullable=True)
    COOKING_CATEGORY_NAME = Column(String(200), nullable=True)
    COOKING_INTRODUCTION = Column(String(4000), nullable=True)
    NUMBER_OF_SERVING = Column(String(200), nullable=True)
    THUMBNAIL_URL = Column(String(200), nullable=True)

    # 재료(FCT_MTRL)와 1:N 관계 설정
    materials = relationship(
        "Material",
        back_populates="recipe",
        primaryjoin="Recipe.RECIPE_ID==Material.RECIPE_ID",
        lazy="joined"
    )

class Material(Base):
    """
    FCT_MTRL 테이블의 ORM 모델
    """
    __tablename__ = "FCT_MTRL"

    MATERIAL_ID = Column(Integer, primary_key=True, autoincrement=True)
    RECIPE_ID = Column(Integer, ForeignKey("FCT_RECIPE.RECIPE_ID"), nullable=True)
    MATERIAL_NAME = Column(String(100), nullable=True)
    MEASURE_AMOUNT = Column(String(100), nullable=True)
    MEASURE_UNIT = Column(String(200), nullable=True)
    DETAILS = Column(String(200), nullable=True)

    # 레시피(FCT_RECIPE)와 N:1 관계 설정
    recipe = relationship(
        "Recipe",
        back_populates="materials",
        lazy="joined"
    )
