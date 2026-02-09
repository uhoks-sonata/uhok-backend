from sqlalchemy import Column, Integer, Text

from common.database.base_mariadb import MariaBase

class KokClassify(MariaBase):
    """
    KOK_CLASSIFY 테이블의 ORM 모델
    콕 제품의 식재료 분류 정보를 저장
    """
    __tablename__ = "KOK_CLASSIFY"

    product_id = Column("PRODUCT_ID", Integer, primary_key=True, autoincrement=False, comment='콕 제품 코드')
    product_name = Column("PRODUCT_NAME", Text, nullable=False, comment='제품명')
    cls_ing = Column("CLS_ING", Integer, nullable=True, comment='식재료 분류')
