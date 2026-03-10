import psycopg2
from app.utils.env import DATABASE_URL

def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def test_connection():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    result = cur.fetchone()
    conn.close()
    return result
