"""
레시피 및 재료(FCT_RECIPE, FCT_MTRL) 테이블의 ORM 모델 정의 모듈
- 변수는 소문자, DB 컬럼명은 대문자로 명시적 매핑
"""

from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger, Text
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from common.database.base_mariadb import MariaBase
from common.database.base_postgres import PostgresBase

class Recipe(MariaBase):
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
        lazy="select"
    )

class Material(MariaBase):
    """
    FCT_MTRL 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    """
    __tablename__ = "FCT_MTRL"

    material_id = Column("MATERIAL_ID", Integer, primary_key=True, autoincrement=True)
    recipe_id = Column("RECIPE_ID", Integer, ForeignKey("FCT_RECIPE.RECIPE_ID", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    material_name = Column("MATERIAL_NAME", String(100), nullable=True)
    measure_amount = Column("MEASURE_AMOUNT", String(100), nullable=True)
    measure_unit = Column("MEASURE_UNIT", String(200), nullable=True)
    details = Column("DETAILS", String(200), nullable=True)

    # 레시피(FCT_RECIPE)와 N:1 관계 설정
    recipe = relationship(
        "Recipe",
        back_populates="materials",
        lazy="select"
    )

class RecipeRating(MariaBase):
    """
    RECIPE_RATING 테이블의 ORM 모델
    변수는 소문자, 컬럼은 대문자 (FK만 연결)
    """
    __tablename__ = "RECIPE_RATING"

    rating_id = Column("RATING_ID", Integer, primary_key=True, autoincrement=True)
    recipe_id = Column("RECIPE_ID", Integer, ForeignKey("FCT_RECIPE.RECIPE_ID", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    user_id = Column("USER_ID", Integer, nullable=False)
    rating = Column("RATING", Integer, nullable=False)   # INT로 변경


###########################################################
# class RecipeComment(MariaBase):
#     """
#     RECIPE_COMMENT 테이블의 ORM 모델
#     변수는 소문자, 컬럼은 대문자 (FK만 연결, Recipe와 직접 relationship 불필요)
#     """
#     __tablename__ = "RECIPE_COMMENT"
#
#     comment_id = Column("COMMENT_ID", Integer, primary_key=True, autoincrement=True)
#     recipe_id = Column("RECIPE_ID", Integer, ForeignKey("FCT_RECIPE.RECIPE_ID"), nullable=False)
#     user_id = Column("USER_ID", Integer, nullable=False)
#     comment = Column("COMMENT", String(1000), nullable=False)


class RecipeVector(PostgresBase):
    """
    RECIPE_VECTOR_TABLE 테이블의 ORM 모델
    PostgreSQL의 벡터 검색을 위한 테이블
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    """
    __tablename__ = "RECIPE_VECTOR_TABLE"

    vector_id = Column("VECTOR_ID", Integer, primary_key=True, autoincrement=True, comment='벡터 고유 ID')
    vector_name = Column("VECTOR_NAME", Vector(384), nullable=True, comment='벡터 이름')
    recipe_id = Column("RECIPE_ID", BigInteger, nullable=True, comment='레시피 고유 ID')