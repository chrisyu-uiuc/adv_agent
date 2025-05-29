import sqlite3
import os

# Define database path
DB_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(DB_DIR, 'restaurant.db')
SCHEMA_PATH = os.path.join(DB_DIR, 'schema.sql')

def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file"""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn

def execute_sql_from_file(conn, sql_file_path):
    """Read SQL commands from a given .sql file and execute them"""
    try:
        with open(sql_file_path, 'r') as f:
            sql_script = f.read()
        cursor = conn.cursor()
        cursor.executescript(sql_script)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error executing SQL from file {sql_file_path}: {e}")
    except IOError as e:
        print(f"Error reading file {sql_file_path}: {e}")

def populate_tables(conn):
    """Populate tables with sample data"""
    try:
        cursor = conn.cursor()

        # Sample tables
        tables_data = [
            (1, 2), (2, 4), (3, 4), (4, 6), (5, 8),
            (10, 2), (11, 3), (12, 4), (15, 6) # More varied table numbers
        ]
        cursor.executemany("INSERT INTO tables (table_number, capacity) VALUES (?, ?)", tables_data)

        # Sample menu items
        menu_items_data = [
            ('Pizza Margherita', 'food', 12.50),
            ('Spaghetti Carbonara', 'food', 15.00),
            ('Caesar Salad', 'food', 9.75),
            ('Bruschetta', 'food', 7.00),
            ('Coca-Cola', 'drink', 2.50),
            ('Orange Juice', 'drink', 3.00),
            ('Red Wine (Glass)', 'drink', 6.00)
        ]
        cursor.executemany("INSERT INTO menu_items (name, category, price) VALUES (?, ?, ?)", menu_items_data)

        conn.commit()
    except sqlite3.Error as e:
        print(f"Error populating tables: {e}")

def main():
    """Main function to create and populate the database"""
    # Remove existing database file to ensure a fresh setup each time
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"Removed existing database: {DB_PATH}")
        except OSError as e:
            print(f"Error removing existing database {DB_PATH}: {e}")
            return # Exit if we cannot remove the old DB

    conn = create_connection(DB_PATH)

    if conn is not None:
        print(f"Database connection to {DB_PATH} established.")
        
        if not os.path.exists(SCHEMA_PATH):
            print(f"Error: Schema file not found at {SCHEMA_PATH}")
            conn.close()
            return

        execute_sql_from_file(conn, SCHEMA_PATH)
        populate_tables(conn)
        
        print(f"Database {DB_PATH} created and populated successfully.")
        
        conn.close()
    else:
        print(f"Error: Could not create the database connection to {DB_PATH}.")

if __name__ == '__main__':
    main()
