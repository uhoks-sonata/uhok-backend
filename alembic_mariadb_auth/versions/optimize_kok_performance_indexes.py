"""optimize_kok_performance_indexes

Revision ID: optimize_kok_performance_indexes
Revises: 6cea6fa1d546
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'optimize_kok_performance_indexes'
down_revision = '6cea6fa1d546'
branch_labels = None
depends_on = None

def upgrade():
    """KOK 성능 최적화를 위한 인덱스 추가"""
    
    # FCT_KOK_PRICE_INFO 테이블 인덱스
    # 1. 할인율 기준 정렬을 위한 복합 인덱스
    op.create_index(
        'idx_kok_price_discount_rate_product_id',
        'FCT_KOK_PRICE_INFO',
        ['KOK_DISCOUNT_RATE', 'KOK_PRODUCT_ID'],
        unique=False
    )
    
    # 2. 상품별 최신 가격 조회를 위한 인덱스
    op.create_index(
        'idx_kok_price_product_id_price_id',
        'FCT_KOK_PRICE_INFO',
        ['KOK_PRODUCT_ID', 'KOK_PRICE_ID'],
        unique=False
    )
    
    # 3. 할인율이 있는 상품만 필터링하기 위한 인덱스
    op.create_index(
        'idx_kok_price_discount_rate_gt_zero',
        'FCT_KOK_PRICE_INFO',
        ['KOK_DISCOUNT_RATE'],
        unique=False,
        postgresql_where=sa.text('KOK_DISCOUNT_RATE > 0')
    )
    
    # FCT_KOK_PRODUCT_INFO 테이블 인덱스
    # 4. 리뷰 개수 기준 정렬을 위한 인덱스
    op.create_index(
        'idx_kok_product_review_cnt_score',
        'FCT_KOK_PRODUCT_INFO',
        ['KOK_REVIEW_CNT', 'KOK_REVIEW_SCORE'],
        unique=False
    )
    
    # 5. 리뷰 점수 기준 정렬을 위한 인덱스
    op.create_index(
        'idx_kok_product_review_score_cnt',
        'FCT_KOK_PRODUCT_INFO',
        ['KOK_REVIEW_SCORE', 'KOK_REVIEW_CNT'],
        unique=False
    )
    
    # 6. 스토어별 상품 조회를 위한 인덱스
    op.create_index(
        'idx_kok_product_store_name',
        'FCT_KOK_PRODUCT_INFO',
        ['KOK_STORE_NAME'],
        unique=False
    )
    
    # 7. 리뷰가 있는 상품만 필터링하기 위한 복합 인덱스
    op.create_index(
        'idx_kok_product_has_reviews',
        'FCT_KOK_PRODUCT_INFO',
        ['KOK_REVIEW_CNT', 'KOK_REVIEW_SCORE'],
        unique=False,
        postgresql_where=sa.text('KOK_REVIEW_CNT > 0')
    )
    
    # 8. 상품명 검색을 위한 인덱스 (LIKE 쿼리 최적화)
    op.create_index(
        'idx_kok_product_name_search',
        'FCT_KOK_PRODUCT_INFO',
        ['KOK_PRODUCT_NAME'],
        unique=False
    )
    
    # 9. 썸네일이 있는 상품만 필터링하기 위한 인덱스
    op.create_index(
        'idx_kok_product_has_thumbnail',
        'FCT_KOK_PRODUCT_INFO',
        ['KOK_THUMBNAIL'],
        unique=False,
        postgresql_where=sa.text("KOK_THUMBNAIL IS NOT NULL AND KOK_THUMBNAIL != ''")
    )

def downgrade():
    """인덱스 제거"""
    
    # FCT_KOK_PRICE_INFO 테이블 인덱스 제거
    op.drop_index('idx_kok_price_discount_rate_product_id', table_name='FCT_KOK_PRICE_INFO')
    op.drop_index('idx_kok_price_product_id_price_id', table_name='FCT_KOK_PRICE_INFO')
    op.drop_index('idx_kok_price_discount_rate_gt_zero', table_name='FCT_KOK_PRICE_INFO')
    
    # FCT_KOK_PRODUCT_INFO 테이블 인덱스 제거
    op.drop_index('idx_kok_product_review_cnt_score', table_name='FCT_KOK_PRODUCT_INFO')
    op.drop_index('idx_kok_product_review_score_cnt', table_name='FCT_KOK_PRODUCT_INFO')
    op.drop_index('idx_kok_product_store_name', table_name='FCT_KOK_PRODUCT_INFO')
    op.drop_index('idx_kok_product_has_reviews', table_name='FCT_KOK_PRODUCT_INFO')
    op.drop_index('idx_kok_product_name_search', table_name='FCT_KOK_PRODUCT_INFO')
    op.drop_index('idx_kok_product_has_thumbnail', table_name='FCT_KOK_PRODUCT_INFO')
