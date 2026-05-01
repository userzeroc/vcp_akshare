
import os
import psycopg2
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

def get_db_stats():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "mysecretpassword"),
            dbname=os.getenv("DB_NAME", "mydb")
        )
        cur = conn.cursor()

        # Get all table names
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
        tables = [t[0] for t in cur.fetchall()]

        stats = {}

        for table in tables:
            # 1. Total records
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            count = cur.fetchone()[0]
            
            min_date, max_date, unique_symbols = "-", "-", "-"
            
            # Check for columns to determine what else to count
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'")
            columns = [c[0] for c in cur.fetchall()]
            
            date_col = next((c for c in columns if c in ['trade_date', 'cal_date', 'date', 'created_at']), None)
            code_col = next((c for c in columns if c in ['ts_code', 'index_code', 'index_id']), None)

            if date_col and count > 0:
                cur.execute(f'SELECT MIN("{date_col}"), MAX("{date_col}") FROM "{table}"')
                min_date, max_date = cur.fetchone()
            
            if code_col and count > 0:
                cur.execute(f'SELECT COUNT(DISTINCT "{code_col}") FROM "{table}"')
                unique_symbols = cur.fetchone()[0]
            
            stats[table] = {
                'count': count,
                'min_date': min_date,
                'max_date': max_date,
                'unique_symbols': unique_symbols,
                'date_col': date_col,
                'code_col': code_col
            }

        # Specific details for stock_basic if it exists
        if 'stock_basic' in stats:
            cur.execute("SELECT list_status, COUNT(*) FROM stock_basic GROUP BY list_status")
            stats['stock_basic']['status'] = dict(cur.fetchall())

        cur.close()
        conn.close()
        return stats

    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    stats = get_db_stats()
    if stats:
        def date_handler(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            else:
                return str(obj)
        print(json.dumps(stats, default=date_handler, indent=2, ensure_ascii=False))
