"""
레시피 및 재료(FCT_RECIPE, FCT_MTRL) 테이블의 ORM 모델 정의 모듈
- 변수는 소문자, DB 컬럼명은 대문자로 명시적 매핑
"""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Recipe(Base):
    """
    FCT_RECIPE 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자 매핑
    """
    __tablename__ = "FCT_RECIPE"

    recipe_id = Column("RECIPE_ID", Integer, primary_key=True, autoincrement=False)
    recipe_title = Column("RECIPE_TITLE", String(200), nullable=True)
    cooking_name = Column("COOKING_NAME", String(40), nullable=True)
    scrap_count = Column("SCRAP_COUNT", Integer, nullable=True)
    cooking_case_name = Column("COOKING_CASE_NAME", String(200), nullable=True)
    cooking_category_name = Column("COOKING_CATEGORY_NAME", String(200), nullable=True)
    cooking_introduction = Column("COOKING_INTRODUCTION", String(4000), nullable=True)
    number_of_serving = Column("NUMBER_OF_SERVING", String(200), nullable=True)
    thumbnail_url = Column("THUMBNAIL_URL", String(200), nullable=True)

    # 재료(FCT_MTRL)와 1:N 관계 설정
    materials = relationship(
        "Material",
        back_populates="recipe",
        primaryjoin="Recipe.recipe_id==Material.recipe_id",
        lazy="joined"
    )

class Material(Base):
    """
    FCT_MTRL 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    """
    __tablename__ = "FCT_MTRL"

    material_id = Column("MATERIAL_ID", Integer, primary_key=True, autoincrement=True)
    recipe_id = Column("RECIPE_ID", Integer, ForeignKey("FCT_RECIPE.RECIPE_ID"), nullable=True)
    material_name = Column("MATERIAL_NAME", String(100), nullable=True)
    measure_amount = Column("MEASURE_AMOUNT", String(100), nullable=True)
    measure_unit = Column("MEASURE_UNIT", String(200), nullable=True)
    details = Column("DETAILS", String(200), nullable=True)

    # 레시피(FCT_RECIPE)와 N:1 관계 설정
    recipe = relationship(
        "Recipe",
        back_populates="materials",
        lazy="joined"
    )
