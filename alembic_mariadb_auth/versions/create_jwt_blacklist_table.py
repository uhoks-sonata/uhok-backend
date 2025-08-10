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
    op.create_table('jwt_blacklist',
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('blacklisted_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('token_hash')
    )
    
    # 인덱스 생성
    op.create_index('ix_jwt_blacklist_token_hash', 'jwt_blacklist', ['token_hash'])
    op.create_index('ix_jwt_blacklist_user_id', 'jwt_blacklist', ['user_id'])
    op.create_index('ix_jwt_blacklist_expires_at', 'jwt_blacklist', ['expires_at'])


def downgrade():
    # 테이블 삭제
    op.drop_index('ix_jwt_blacklist_expires_at', table_name='jwt_blacklist')
    op.drop_index('ix_jwt_blacklist_user_id', table_name='jwt_blacklist')
    op.drop_index('ix_jwt_blacklist_token_hash', table_name='jwt_blacklist')
    op.drop_table('jwt_blacklist')
