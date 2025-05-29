import sqlite3
import os

# Define database path
CORE_LOGIC_DIR = os.path.dirname(__file__)
DB_DIR = os.path.abspath(os.path.join(CORE_LOGIC_DIR, '..', 'database'))
DB_PATH = os.path.join(DB_DIR, 'restaurant.db')

def get_db_connection():
    """
    Creates and returns a database connection to the SQLite database.
    Enables row factory for dictionary-like row access.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database at {DB_PATH}: {e}")
        return None

if __name__ == '__main__':
    # This block can be used for basic testing of the get_db_connection function.
    # For example, uncomment the lines below to test the connection.
    # print(f"DB_PATH is: {DB_PATH}") # For debugging path issues
    # conn = get_db_connection()
    # if conn:
    #     print("Database connection successful (when called directly).")
    #     conn.close()
    # else:
    #     print("Database connection failed (when called directly).")
    pass
