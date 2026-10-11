"""
sql_guard.py — validates LLM-generated SQL BEFORE it reaches the database.

This is layer 2 of the Text-to-SQL sandbox. Layer 1 lives in Postgres
(`database.agent_readonly_session`: READ ONLY transaction, a role that can only
SELECT from the user-scoped views, statement timeout). Layer 2 exists because
any Postgres role may call set_config(), so the DB alone cannot stop generated
SQL from touching the `app.current_user_id` setting. Here we parse the SQL and
accept only what is provably harmless:

  * exactly ONE statement, and it is a plain SELECT (WITH ... SELECT included;
    no UNION, INTO, locking clauses, DDL, DML, COPY, SET ...)
  * only the two agent views (plus the query's own CTE names), never
    schema-qualified
  * only functions on an explicit allow-list: no set_config, current_setting,
    pg_*, version(), ... (an allow-list, not a deny-list: unknown == rejected)
  * a row cap is enforced, and the SQL that is executed is REGENERATED from the
    AST, so comments or smuggled syntax cannot survive.
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

ALLOWED_TABLES = frozenset({"agent_transactions", "agent_budgets"})
MAX_ROWS = 100

ALLOWED_FUNCTIONS = frozenset({
    # aggregates
    "SUM", "AVG", "COUNT", "MIN", "MAX", "STDDEV", "STDDEV_POP", "STDDEV_SAMP", "VARIANCE", "PERCENTILE_CONT",
    "PERCENTILE_DISC", "MEDIAN",
    # math
    "ROUND", "ABS", "CEIL", "CEILING", "FLOOR", "GREATEST", "LEAST", "SQRT", "POWER", "LN", "LOG",
    # null / conditional / cast
    "COALESCE", "NULLIF", "CASE", "IF", "CAST", "TRY_CAST",
    # text
    "LOWER", "UPPER", "LENGTH", "TRIM", "SUBSTRING", "CONCAT", "CONCAT_WS", "LEFT", "RIGHT", "REPLACE",
    # dates (all evaluated in the session time zone set by the sandbox)
    "DATE_TRUNC", "TIMESTAMP_TRUNC", "TIMESTAMPTZ_TRUNC", "DATE_ADD", "DATE_SUB", "TIMESTAMP_ADD", "TIMESTAMP_SUB", "EXTRACT", "DATE_PART", "TO_CHAR", "TIME_TO_STR", "NOW", "CURRENT_DATE", "CURRENT_TIMESTAMP", "AGE",
    # window functions
    "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE", "NTILE",
})


class SQLGuardError(ValueError):
    """Raised with a message safe (and useful) to feed back to the LLM for self-correction."""


def _func_name(node: exp.Func) -> str:
    return (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).upper()


def validate_and_limit(sql: str, max_rows: int = MAX_ROWS) -> str:
    """Return a safe, row-capped, regenerated SQL string, or raise SQLGuardError."""
    if not sql or not sql.strip():
        raise SQLGuardError("Empty query.")
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except SqlglotError as e:
        raise SQLGuardError(f"SQL syntax error: {str(e).splitlines()[0][:200]}") from None

    if len(statements) != 1:
        raise SQLGuardError("Exactly one SQL statement is allowed.")
    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise SQLGuardError("Only a single SELECT query is allowed (no UNION, DML, DDL, SET or COPY).")
    if tree.find(exp.Into) or tree.find(exp.Lock):
        raise SQLGuardError("SELECT ... INTO and locking clauses are not allowed.")

    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if table.args.get("db") or table.args.get("catalog"):
            raise SQLGuardError("Schema-qualified tables are not allowed. Use agent_transactions or agent_budgets.")
        name = table.name.lower()
        if name not in ALLOWED_TABLES and name not in ctes:
            raise SQLGuardError(
                f"Table '{table.name}' is not available. Allowed tables: {', '.join(sorted(ALLOWED_TABLES))}."
            )

    for fn in tree.find_all(exp.Func):
        if isinstance(fn, (exp.Binary, exp.Unary, exp.Connector)):
            continue  # sqlglot models AND / OR / + / - / NOT as Func subclasses; they are operators, not calls
        if _func_name(fn) not in ALLOWED_FUNCTIONS:
            raise SQLGuardError(f"Function '{_func_name(fn).lower()}' is not allowed.")

    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(max_rows)
    else:
        try:
            requested = int(limit.expression.name)
        except (AttributeError, ValueError):
            raise SQLGuardError("LIMIT must be a plain integer.") from None
        if requested > max_rows:
            tree = tree.limit(max_rows)
    return tree.sql(dialect="postgres", comments=False)  # no attacker-controlled comment text survives
