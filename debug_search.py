from app import get_db_connection
import sys

def test_search(query):
    print(f"Testing search for: '{query}'")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = """
        SELECT U.USERID, U.NAME, U.BADGENUMBER, U.IsActive
        FROM [AURAHR].[dbo].[USERINFO] U
        WHERE (U.BADGENUMBER = ?) OR (U.NAME LIKE ?) OR (TRY_CAST(U.BADGENUMBER AS BIGINT) = TRY_CAST(? AS BIGINT))
        ORDER BY U.IsActive DESC
    """
    
    try:
        cursor.execute(sql, (query, f"%{query}%", query))
        rows = cursor.fetchall()
        print(f"Found {len(rows)} rows.")
        for row in rows:
            print(f"Row: {row}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_search('401')
