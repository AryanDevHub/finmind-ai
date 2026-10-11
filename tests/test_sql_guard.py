"""SQL guard: the AST allow-list for LLM-generated SQL (pure unit tests, no database)."""
import pytest

from backend.sql_guard import MAX_ROWS, SQLGuardError, validate_and_limit

GOOD = [
    "SELECT SUM(amount) FROM agent_transactions WHERE transaction_type='expense' AND category='Food'",
    "SELECT SUM(amount) FROM agent_transactions WHERE occurred_at >= date_trunc('month', now() - interval '1 month') AND occurred_at < date_trunc('month', now())",
    "WITH m AS (SELECT date_trunc('month', occurred_at) AS mo, SUM(amount) AS s FROM agent_transactions GROUP BY 1) SELECT * FROM m ORDER BY mo",
    "SELECT occurred_at::date d, SUM(amount) FROM agent_transactions WHERE occurred_at >= current_date - interval '30 days' GROUP BY 1",
    "SELECT EXTRACT(month FROM occurred_at) m, COUNT(DISTINCT category), AVG(amount) FROM agent_transactions GROUP BY 1",
    "SELECT to_char(occurred_at,'YYYY-MM') mo, SUM(amount) FROM agent_transactions GROUP BY 1",
    "SELECT category, SUM(amount) / NULLIF((SELECT SUM(amount) FROM agent_transactions),0) * 100 pct FROM agent_transactions GROUP BY 1",
    "SELECT description, RANK() OVER (PARTITION BY category ORDER BY amount DESC) r FROM agent_transactions",
    "SELECT * FROM agent_transactions WHERE is_flagged = true OR risk_level IN ('HIGH','CRITICAL')",
    "SELECT category, limit_amount - spent_amount remaining FROM agent_budgets WHERE month = to_char(now(),'YYYY-MM')",
    "SELECT description FROM agent_transactions WHERE description ILIKE '%foo:bar%'",
    "SELECT SUM(amount) FILTER (WHERE category='Food') FROM agent_transactions",
]

BAD = [
    "SELECT * FROM users", "SELECT * FROM transactions", "SELECT * FROM refresh_tokens",
    "SELECT * FROM public.agent_transactions", "SELECT * FROM pg_catalog.pg_tables",
    "SELECT set_config('app.current_user_id','00000000-0000-0000-0000-000000000000',true)",
    "SELECT current_setting('app.current_user_id')", "SELECT pg_sleep(10)", "SELECT version()",
    "SELECT pg_read_file('/etc/passwd')", "SELECT lo_import('/etc/passwd')",
    "SELECT SUM(amount) AND pg_sleep(5) FROM agent_transactions",
    "SELECT 1 WHERE true AND current_setting('app.current_user_id') = 'x'",
    "SELECT (SELECT set_config('a','b',true))",
    "DELETE FROM agent_transactions", "DROP TABLE users", "UPDATE budgets SET limit_amount = 1",
    "INSERT INTO budgets(id) VALUES (gen_random_uuid())", "TRUNCATE agent_transactions",
    "SELECT 1; DROP TABLE users", "SELECT 1; SELECT 2",
    "SELECT * FROM agent_transactions UNION SELECT * FROM agent_transactions",
    "SELECT * INTO newtab FROM agent_transactions", "SELECT * FROM agent_transactions FOR UPDATE",
    "COPY agent_transactions TO '/tmp/x'", "SET ROLE postgres", "RESET ROLE",
    "SELECT * FROM agent_transactions WHERE id IN (SELECT id FROM users)",
    "SELEC oops", "", "   ", "SELECT * FROM generate_series(1,10)",
]


@pytest.mark.parametrize("sql", GOOD)
def test_allows_legitimate_analytics(sql: str) -> None:
    out = validate_and_limit(sql)
    assert out.upper().startswith(("SELECT", "WITH"))
    assert "LIMIT" in out.upper()


@pytest.mark.parametrize("sql", BAD)
def test_rejects_everything_else(sql: str) -> None:
    with pytest.raises(SQLGuardError):
        validate_and_limit(sql)


def test_row_cap_is_enforced() -> None:
    assert f"LIMIT {MAX_ROWS}" in validate_and_limit("SELECT * FROM agent_transactions")
    assert f"LIMIT {MAX_ROWS}" in validate_and_limit("SELECT * FROM agent_transactions LIMIT 100000")
    assert "LIMIT 5" in validate_and_limit("SELECT * FROM agent_transactions LIMIT 5")


def test_comments_do_not_survive_regeneration() -> None:
    for sql in ("SELECT 1 FROM agent_transactions -- ; DROP TABLE users",
                "SELECT 1 FROM agent_transactions /* x */ DROP /* y */",
                "SELECT 1 FROM agent_transactions -- */ DROP TABLE users; /*"):
        try:
            out = validate_and_limit(sql)
        except SQLGuardError:
            continue
        assert "DROP" not in out.upper() and "/*" not in out and "--" not in out
