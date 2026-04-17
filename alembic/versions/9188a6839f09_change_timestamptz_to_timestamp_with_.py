"""change_timestamptz_to_timestamp_with_beijing_timezone

Revision ID: 9188a6839f09
Revises: 
Create Date: 2026-04-17 13:49:05.697003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9188a6839f09'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 修改 reviews 表
    op.execute("""
        ALTER TABLE reviews
        ALTER COLUMN created_at
        TYPE TIMESTAMP
        USING created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai',
        ALTER COLUMN created_at
        SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai');
    """)

    op.execute("""
        ALTER TABLE reviews
        ALTER COLUMN completed_at
        TYPE TIMESTAMP
        USING completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai';
    """)

    # 修改 review_findings 表
    op.execute("""
        ALTER TABLE review_findings
        ALTER COLUMN created_at
        TYPE TIMESTAMP
        USING created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai',
        ALTER COLUMN created_at
        SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai');
    """)

    # 修改 pr_files 表
    op.execute("""
        ALTER TABLE pr_files
        ALTER COLUMN created_at
        TYPE TIMESTAMP
        USING created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai',
        ALTER COLUMN created_at
        SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai');
    """)

    # 修改 bug_knowledge 表
    op.execute("""
        ALTER TABLE bug_knowledge
        ALTER COLUMN created_at
        TYPE TIMESTAMP
        USING created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai',
        ALTER COLUMN created_at
        SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai');
    """)

    # 修改 developer_feedback 表
    op.execute("""
        ALTER TABLE developer_feedback
        ALTER COLUMN created_at
        TYPE TIMESTAMP
        USING created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai',
        ALTER COLUMN created_at
        SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai');
    """)

    # 修改 project_configs 表
    op.execute("""
        ALTER TABLE project_configs
        ALTER COLUMN updated_at
        TYPE TIMESTAMP
        USING updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai',
        ALTER COLUMN updated_at
        SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai');
    """)

    # 修改 file_dependencies 表
    op.execute("""
        ALTER TABLE file_dependencies
        ALTER COLUMN created_at
        TYPE TIMESTAMP
        USING created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai',
        ALTER COLUMN created_at
        SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai');
    """)

    # 修改 prompt_experiments 表
    op.execute("""
        ALTER TABLE prompt_experiments
        ALTER COLUMN created_at
        TYPE TIMESTAMP
        USING created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai',
        ALTER COLUMN created_at
        SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai');
    """)

    # 修改 prompt_experiment_assignments 表
    op.execute("""
        ALTER TABLE prompt_experiment_assignments
        ALTER COLUMN created_at
        TYPE TIMESTAMP
        USING created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai',
        ALTER COLUMN created_at
        SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai');
    """)


def downgrade() -> None:
    # 恢复为 TIMESTAMPTZ
    op.execute("""
        ALTER TABLE reviews
        ALTER COLUMN created_at
        TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'Asia/Shanghai' AT TIME ZONE 'UTC',
        ALTER COLUMN created_at
        SET DEFAULT CURRENT_TIMESTAMP;
    """)

    op.execute("""
        ALTER TABLE reviews
        ALTER COLUMN completed_at
        TYPE TIMESTAMPTZ
        USING completed_at AT TIME ZONE 'Asia/Shanghai' AT TIME ZONE 'UTC';
    """)

    op.execute("""
        ALTER TABLE review_findings
        ALTER COLUMN created_at
        TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'Asia/Shanghai' AT TIME ZONE 'UTC',
        ALTER COLUMN created_at
        SET DEFAULT CURRENT_TIMESTAMP;
    """)

    op.execute("""
        ALTER TABLE pr_files
        ALTER COLUMN created_at
        TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'Asia/Shanghai' AT TIME ZONE 'UTC',
        ALTER COLUMN created_at
        SET DEFAULT CURRENT_TIMESTAMP;
    """)

    op.execute("""
        ALTER TABLE bug_knowledge
        ALTER COLUMN created_at
        TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'Asia/Shanghai' AT TIME ZONE 'UTC',
        ALTER COLUMN created_at
        SET DEFAULT CURRENT_TIMESTAMP;
    """)

    op.execute("""
        ALTER TABLE developer_feedback
        ALTER COLUMN created_at
        TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'Asia/Shanghai' AT TIME ZONE 'UTC',
        ALTER COLUMN created_at
        SET DEFAULT CURRENT_TIMESTAMP;
    """)

    op.execute("""
        ALTER TABLE project_configs
        ALTER COLUMN updated_at
        TYPE TIMESTAMPTZ
        USING updated_at AT TIME ZONE 'Asia/Shanghai' AT TIME ZONE 'UTC',
        ALTER COLUMN updated_at
        SET DEFAULT CURRENT_TIMESTAMP;
    """)

    op.execute("""
        ALTER TABLE file_dependencies
        ALTER COLUMN created_at
        TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'Asia/Shanghai' AT TIME ZONE 'UTC',
        ALTER COLUMN created_at
        SET DEFAULT CURRENT_TIMESTAMP;
    """)

    op.execute("""
        ALTER TABLE prompt_experiments
        ALTER COLUMN created_at
        TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'Asia/Shanghai' AT TIME ZONE 'UTC',
        ALTER COLUMN created_at
        SET DEFAULT CURRENT_TIMESTAMP;
    """)

    op.execute("""
        ALTER TABLE prompt_experiment_assignments
        ALTER COLUMN created_at
        TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'Asia/Shanghai' AT TIME ZONE 'UTC',
        ALTER COLUMN created_at
        SET DEFAULT CURRENT_TIMESTAMP;
    """)
