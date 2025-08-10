"""create jwt blacklist table

Revision ID: create_jwt_blacklist_table
Revises: 6cea6fa1d546
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'create_jwt_blacklist_table'
down_revision = '6cea6fa1d546'
branch_labels = None
depends_on = None


def upgrade():
    # JWT 블랙리스트 테이블 생성
    op.create_table('JWT_BLACKLIST',
        sa.Column('TOKEN_HASH', sa.String(255), nullable=False),
        sa.Column('BLACKLISTED_AT', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('EXPIRES_AT', sa.DateTime(timezone=True), nullable=False),
        sa.Column('USER_ID', sa.String(36), nullable=True),
        sa.Column('METADATA', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('TOKEN_HASH')
    )
    
    # 인덱스 생성
    op.create_index('ix_JWT_BLACKLIST_TOKEN_HASH', 'JWT_BLACKLIST', ['TOKEN_HASH'])
    op.create_index('ix_JWT_BLACKLIST_USER_ID', 'JWT_BLACKLIST', ['USER_ID'])
    op.create_index('ix_JWT_BLACKLIST_EXPIRES_AT', 'JWT_BLACKLIST', ['EXPIRES_AT'])


def downgrade():
    # 테이블 삭제
    op.drop_index('ix_JWT_BLACKLIST_EXPIRES_AT', table_name='JWT_BLACKLIST')
    op.drop_index('ix_JWT_BLACKLIST_USER_ID', table_name='JWT_BLACKLIST')
    op.drop_index('ix_JWT_BLACKLIST_TOKEN_HASH', table_name='JWT_BLACKLIST')
    op.drop_table('JWT_BLACKLIST')
