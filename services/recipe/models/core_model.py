"""Core MariaDB recipe models."""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase


class Recipe(MariaBase):
    """FCT_RECIPE 테이블의 ORM 모델."""

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

    materials = relationship(
        "Material",
        back_populates="recipe",
        primaryjoin="Recipe.recipe_id==Material.recipe_id",
        lazy="select",
    )


class Material(MariaBase):
    """FCT_MTRL 테이블의 ORM 모델."""

    __tablename__ = "FCT_MTRL"

    material_id = Column("MATERIAL_ID", Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(
        "RECIPE_ID",
        Integer,
        ForeignKey("FCT_RECIPE.RECIPE_ID", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    material_name = Column("MATERIAL_NAME", String(100), nullable=True)
    measure_amount = Column("MEASURE_AMOUNT", String(100), nullable=True)
    measure_unit = Column("MEASURE_UNIT", String(200), nullable=True)
    details = Column("DETAILS", String(200), nullable=True)

    recipe = relationship("Recipe", back_populates="materials", lazy="select")


class RecipeRating(MariaBase):
    """RECIPE_RATING 테이블의 ORM 모델."""

    __tablename__ = "RECIPE_RATING"

    rating_id = Column("RATING_ID", Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(
        "RECIPE_ID",
        Integer,
        ForeignKey("FCT_RECIPE.RECIPE_ID", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column("USER_ID", Integer, nullable=False)
    rating = Column("RATING", Integer, nullable=False)
