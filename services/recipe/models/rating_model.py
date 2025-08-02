# services/recipe/models/rating_model.py
from sqlalchemy import Column, Integer, Float
from sqlalchemy.orm import declarative_base
Base = declarative_base()

class Rating(Base):
    __tablename__ = "RATING"
    rating_id = Column("ID", Integer, primary_key=True)
    recipe_id = Column("RECIPE_ID", Integer)
    rating = Column("RATING", Float)
