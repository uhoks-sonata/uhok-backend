"""PostgreSQL vector model for recipe similarity."""

from sqlalchemy import BigInteger, Column, Integer
from pgvector.sqlalchemy import Vector

from common.database.base_postgres import PostgresBase


class RecipeVector(PostgresBase):
    """RECIPE_VECTOR_TABLE 테이블의 ORM 모델."""

    __tablename__ = "RECIPE_VECTOR_TABLE"

    vector_id = Column("VECTOR_ID", Integer, primary_key=True, autoincrement=True, comment="벡터 고유 ID")
    vector_name = Column("VECTOR_NAME", Vector(384), nullable=True, comment="벡터 이름")
    recipe_id = Column("RECIPE_ID", BigInteger, nullable=True, comment="레시피 고유 ID")
