"""initial schema: users, transactions (pgvector), budgets, refresh_tokens, agent sandbox

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-04 09:00:00
"""
from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 384
AGENT_ROLE = "finmind_agent_ro"

_NOW = sa.text("now()")


def upgrade() -> None:
    # ── Extension ────────────────────────────────────────────────────────
    # Needs a role allowed to CREATE EXTENSION (superuser, or trusted-extension
    # privileges on managed Postgres). pgvector/pgvector:pg16 ships the binaries.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── users ────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )

    # ── transactions ─────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("merchant", sa.String(120), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("transaction_type", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("fraud_score", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("risk_level", sa.String(8), server_default="LOW", nullable=False),
        sa.Column("is_flagged", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("fraud_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_version", sa.String(32), nullable=True),
        sa.Column("anomaly_score", sa.Float(), nullable=True),
        sa.Column("is_anomaly", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("anomaly_method", sa.String(24), nullable=True),
        sa.Column("anomaly_scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        sa.CheckConstraint("transaction_type IN ('income', 'expense')", name="type_valid"),
        sa.CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="risk_level_valid"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_user_occurred", "transactions", ["user_id", sa.text("occurred_at DESC")])
    op.create_index(
        "ix_transactions_user_category_occurred",
        "transactions",
        ["user_id", "category", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "ix_transactions_flagged", "transactions", ["user_id", "occurred_at"],
        postgresql_where=sa.text("is_flagged"),
    )
    op.create_index(
        "ix_transactions_pending_embedding", "transactions", ["created_at"],
        postgresql_where=sa.text("embedding IS NULL"),
    )
    # Approximate nearest-neighbour index for cosine similarity (<=>) over description/merchant embeddings.
    op.create_index(
        "ix_transactions_embedding_hnsw",
        "transactions",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # ── budgets ──────────────────────────────────────────────────────────
    op.create_table(
        "budgets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("limit_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("spent_amount", sa.Numeric(14, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.CheckConstraint("limit_amount > 0", name="limit_positive"),
        sa.CheckConstraint("month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name="month_format"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "category", "month", name="uq_budgets_user_category_month"),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])

    # ── refresh_tokens ───────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])

    # ── Text-to-SQL sandbox: user-scoped views + read-only role ──────────
    # The views filter on the `app.current_user_id` setting that the backend
    # sets (transaction-locally) from the authenticated session. Unset => NULL
    # => zero rows. Views execute with the owner's rights, so the role below
    # needs SELECT on the views only and no access to any base table.
    #
    # Known limit: any role may call set_config(); the DB layer alone therefore
    # cannot stop generated SQL from changing the setting. The agent's SQL
    # validator (AST allow-list: single SELECT, agent_* relations only, no
    # set_config/current_setting/pg_* calls) is the required second layer.
    op.execute(
        """
        CREATE VIEW agent_transactions AS
        SELECT id, occurred_at, occurred_at::date AS occurred_date, amount, category,
               transaction_type, description, merchant, is_flagged, risk_level, fraud_score
        FROM transactions
        WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        """
    )
    op.execute(
        """
        CREATE VIEW agent_budgets AS
        SELECT category, limit_amount, spent_amount, month
        FROM budgets
        WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{AGENT_ROLE}') THEN
                CREATE ROLE {AGENT_ROLE} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$
        """
    )
    # The application's login role must be able to `SET ROLE` into the sandbox role.
    op.execute(f"GRANT {AGENT_ROLE} TO CURRENT_USER")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {AGENT_ROLE}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {AGENT_ROLE}")
    op.execute(f"GRANT SELECT ON agent_transactions, agent_budgets TO {AGENT_ROLE}")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS agent_budgets")
    op.execute("DROP VIEW IF EXISTS agent_transactions")
    # Roles are CLUSTER-wide, so we only remove this database's privileges and deliberately leave
    # the role in place: other databases on the same server (dev vs test) may still depend on it.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{AGENT_ROLE}') THEN
                DROP OWNED BY {AGENT_ROLE};
            END IF;
        END
        $$
        """
    )
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_budgets_user_id", table_name="budgets")
    op.drop_table("budgets")
    op.drop_index("ix_transactions_embedding_hnsw", table_name="transactions", postgresql_using="hnsw")
    op.drop_index("ix_transactions_pending_embedding", table_name="transactions")
    op.drop_index("ix_transactions_flagged", table_name="transactions")
    op.drop_index("ix_transactions_user_category_occurred", table_name="transactions")
    op.drop_index("ix_transactions_user_occurred", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("users")
    # The `vector` extension is intentionally left installed (other objects may depend on it).
