"""bank sync and rls

Revision ID: 0002_bank_sync_rls
Revises: 0001_initial
Create Date: 2026-10-11 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_bank_sync_rls"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create bank_connections table
    op.create_table(
        "bank_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("consent_id", sa.String(length=128), nullable=False),
        sa.Column("consent_handle", sa.String(length=128), nullable=True),
        sa.Column("fip_id", sa.String(length=64), nullable=False),
        sa.Column("fip_name", sa.String(length=128), nullable=False),
        sa.Column("phone_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("consent_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_expiry", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("encrypted_consent_artifact", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'REVOKED', 'EXPIRED')",
            name="ck_bank_connections_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_bank_connections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_connections")),
        sa.UniqueConstraint("consent_id", name=op.f("uq_bank_connections_consent_id")),
    )
    op.create_index(op.f("ix_bank_connections_user_id"), "bank_connections", ["user_id"], unique=False)

    # 2. Add bank_txn_hash column (String(64), nullable, unique) to transactions
    op.add_column("transactions", sa.Column("bank_txn_hash", sa.String(length=64), nullable=True))
    op.create_unique_constraint(op.f("uq_transactions_bank_txn_hash"), "transactions", ["bank_txn_hash"])

    # 3. Add source column (String(16), default 'manual', server_default='manual') to transactions
    op.add_column(
        "transactions",
        sa.Column("source", sa.String(length=16), server_default="manual", nullable=False),
    )

    # 4. Enable Row-Level Security (RLS) on transactions and budgets
    # The app's login role (table owner) is exempted because FORCE ROW LEVEL SECURITY is NOT set.
    op.execute("ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY user_isolation_transactions ON transactions
        USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
    """)
    op.execute("""
        CREATE POLICY user_isolation_budgets ON budgets
        USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
    """)

    # 5. Update agent_transactions view to include source column
    op.execute("""
        CREATE OR REPLACE VIEW agent_transactions AS
        SELECT
            id,
            occurred_at,
            occurred_at::date AS occurred_date,
            amount,
            category,
            transaction_type,
            description,
            merchant,
            is_flagged,
            risk_level,
            fraud_score,
            source
        FROM transactions
        WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'finmind_agent_ro') THEN
                GRANT SELECT ON agent_transactions TO finmind_agent_ro;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # 5. Revert agent_transactions view to exclude source column
    op.execute("""
        CREATE OR REPLACE VIEW agent_transactions AS
        SELECT
            id,
            occurred_at,
            occurred_at::date AS occurred_date,
            amount,
            category,
            transaction_type,
            description,
            merchant,
            is_flagged,
            risk_level,
            fraud_score
        FROM transactions
        WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid;
    """)

    # 4. Drop RLS policies and disable RLS
    op.execute("DROP POLICY IF EXISTS user_isolation_budgets ON budgets;")
    op.execute("DROP POLICY IF EXISTS user_isolation_transactions ON transactions;")
    op.execute("ALTER TABLE budgets DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE transactions DISABLE ROW LEVEL SECURITY;")

    # 3. Drop source column
    op.drop_column("transactions", "source")

    # 2. Drop bank_txn_hash column and unique constraint
    op.drop_constraint(op.f("uq_transactions_bank_txn_hash"), "transactions", type_="unique")
    op.drop_column("transactions", "bank_txn_hash")

    # 1. Drop bank_connections table and index
    op.drop_index(op.f("ix_bank_connections_user_id"), table_name="bank_connections")
    op.drop_table("bank_connections")
