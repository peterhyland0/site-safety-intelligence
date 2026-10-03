from ssi.store.pg import dsn


def test_drops_prisma_only_options_from_supabase_strings():
    assert dsn("postgresql://u:p@h:6543/postgres?pgbouncer=true") == "postgresql://u:p@h:6543/postgres"
    assert dsn("postgresql://u:p@h:6543/postgres?pgbouncer=true&sslmode=require") == "postgresql://u:p@h:6543/postgres?sslmode=require"


def test_leaves_plain_urls_alone():
    assert dsn("postgresql://localhost:5432/ssi") == "postgresql://localhost:5432/ssi"
