import sqlite3
from .db_manager import get_db_connection, DB_PATH # DB_PATH might not be needed but good to import if direct path use cases arise

def find_available_tables(num_guests, datetime_str):
    """
    Finds tables available for a given number of guests at a specific time.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return [] # Failed to get connection

        cursor = conn.cursor()
        query = """
            SELECT t.id, t.table_number, t.capacity
            FROM tables t
            WHERE t.capacity >= ?
            AND t.id NOT IN (
                SELECT r.table_id
                FROM reservations r
                WHERE r.reservation_time = ?
            )
            ORDER BY t.capacity;
        """
        cursor.execute(query, (num_guests, datetime_str))
        tables_data = cursor.fetchall()
        
        available_tables = []
        for row in tables_data:
            available_tables.append({'table_id': row['id'], 'table_number': row['table_number'], 'capacity': row['capacity']})
        return available_tables
    except sqlite3.Error as e:
        print(f"Database error in find_available_tables: {e}")
        return []
    finally:
        if conn:
            conn.close()

def book_table(table_id, guest_name, num_guests, datetime_str):
    """
    Books a table for a guest if available and validation passes.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return {'success': False, 'message': 'Failed to connect to database.'}

        cursor = conn.cursor()

        # Validation 1: Check table capacity
        cursor.execute("SELECT capacity FROM tables WHERE id = ?", (table_id,))
        table_row = cursor.fetchone()
        if not table_row:
            return {'success': False, 'message': 'Table not found.'}
        
        table_capacity = table_row['capacity']
        if num_guests > table_capacity:
            return {'success': False, 'message': f'Number of guests ({num_guests}) exceeds table capacity ({table_capacity}).'}

        # Validation 2: Check if table is already booked at that time
        cursor.execute("SELECT id FROM reservations WHERE table_id = ? AND reservation_time = ?", (table_id, datetime_str))
        existing_reservation = cursor.fetchone()
        if existing_reservation:
            return {'success': False, 'message': 'Table is already booked at this time.'}

        # Insert new reservation
        insert_query = """
            INSERT INTO reservations (table_id, guest_name, num_guests, reservation_time)
            VALUES (?, ?, ?, ?);
        """
        cursor.execute(insert_query, (table_id, guest_name, num_guests, datetime_str))
        new_id = cursor.lastrowid
        conn.commit()
        
        return {'success': True, 'reservation_id': new_id, 'message': 'Table booked successfully.'}
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        print(f"Database error in book_table: {e}")
        return {'success': False, 'message': f'Error booking table: {e}'}
    finally:
        if conn:
            conn.close()

def cancel_reservation(reservation_id):
    """
    Cancels an existing reservation by its ID.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return {'success': False, 'message': 'Failed to connect to database.'}

        cursor = conn.cursor()
        
        # Check if reservation exists before attempting to delete (optional, as DELETE itself won't error if not found)
        # cursor.execute("SELECT id FROM reservations WHERE id = ?", (reservation_id,))
        # if not cursor.fetchone():
        #     return {'success': False, 'message': 'Reservation not found.'}

        delete_query = "DELETE FROM reservations WHERE id = ?;"
        cursor.execute(delete_query, (reservation_id,))
        
        if cursor.rowcount > 0:
            conn.commit()
            return {'success': True, 'message': 'Reservation cancelled successfully.'}
        else:
            # No rows were deleted, meaning the reservation_id was not found.
            # No need to rollback as DELETE is a single operation and nothing changed.
            return {'success': False, 'message': 'Reservation not found.'}
            
    except sqlite3.Error as e:
        if conn:
            conn.rollback() # Rollback in case of other errors during the transaction
        print(f"Database error in cancel_reservation: {e}")
        return {'success': False, 'message': f'Error cancelling reservation: {e}'}
    finally:
        if conn:
            conn.close()

def get_reservation_details(reservation_id):
    """
    Retrieves details for a specific reservation.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return None # Failed to get connection

        cursor = conn.cursor()
        query = """
            SELECT r.id, r.guest_name, r.num_guests, r.reservation_time, 
                   t.table_number, t.capacity AS table_capacity
            FROM reservations r
            JOIN tables t ON r.table_id = t.id
            WHERE r.id = ?;
        """
        cursor.execute(query, (reservation_id,))
        reservation_data = cursor.fetchone()
        
        if reservation_data:
            return dict(reservation_data) # Convert sqlite3.Row to dict
        else:
            return None
    except sqlite3.Error as e:
        print(f"Database error in get_reservation_details: {e}")
        return None
    finally:
        if conn:
            conn.close()

def view_menu():
    """
    Retrieves all items from the menu_items table.
    """
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return [] # Failed to get connection

        cursor = conn.cursor()
        query = "SELECT id, name, category, price FROM menu_items ORDER BY category, name;"
        cursor.execute(query)
        menu_data = cursor.fetchall()
        
        menu_items = []
        for row in menu_data:
            menu_items.append(dict(row)) # Convert sqlite3.Row to dict
        return menu_items
    except sqlite3.Error as e:
        print(f"Database error in view_menu: {e}")
        return []
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # This block is for basic manual testing of the functions.
    # It requires the database to be set up (run setup_db.py first).
    print("Running reservation_service.py for basic tests...")
    print(f"Using database at: {DB_PATH}")

    # Ensure DB exists for testing
    import os
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Please run setup_db.py first.")
    else:
        print("\n--- Testing find_available_tables ---")
        # Assuming table setup: (1,2), (2,4), (3,4), (4,6), (5,8), (10,2), (11,3), (12,4), (15,6)
        available = find_available_tables(num_guests=3, datetime_str="2024-08-15 19:00:00")
        if available:
            print(f"Found {len(available)} available tables for 3 guests at 2024-08-15 19:00:00:")
            for table in available:
                print(table)
        else:
            print("No tables found or error.")

        print("\n--- Testing book_table ---")
        # Try to book an available table (e.g., table_id from the above search, if any)
        # Let's assume table with id 2 (table_number 2, capacity 4) is available
        if available and any(t['table_id'] == 2 for t in available):
            booking_result = book_table(table_id=2, guest_name="John Doe", num_guests=2, datetime_str="2024-08-15 19:00:00")
            print(f"Booking result: {booking_result}")
            reservation_id_to_test = booking_result.get('reservation_id')

            if reservation_id_to_test:
                print("\n--- Testing get_reservation_details ---")
                details = get_reservation_details(reservation_id_to_test)
                if details:
                    print(f"Details for reservation {reservation_id_to_test}: {details}")
                else:
                    print(f"Could not get details for reservation {reservation_id_to_test}.")

                print("\n--- Testing find_available_tables (after booking) ---")
                available_after_booking = find_available_tables(num_guests=3, datetime_str="2024-08-15 19:00:00")
                print(f"Available tables for 3 guests (should be one less or table 2 gone): {available_after_booking}")


                print("\n--- Testing cancel_reservation ---")
                cancel_result = cancel_reservation(reservation_id_to_test)
                print(f"Cancel result for reservation {reservation_id_to_test}: {cancel_result}")

                print("\n--- Testing get_reservation_details (after cancelling) ---")
                details_after_cancel = get_reservation_details(reservation_id_to_test)
                if details_after_cancel:
                    print(f"Details for reservation {reservation_id_to_test} (should be None): {details_after_cancel}")
                else:
                    print(f"Reservation {reservation_id_to_test} correctly not found after cancellation.")
        else:
            print("Skipping booking tests as suitable table not found or initial search failed.")
            
        # Test booking a non-existent table
        print("\n--- Testing book_table (non-existent table) ---")
        booking_non_existent = book_table(table_id=999, guest_name="Test", num_guests=2, datetime_str="2024-08-15 20:00:00")
        print(f"Booking non-existent table result: {booking_non_existent}")

        # Test booking with too many guests
        print("\n--- Testing book_table (too many guests) ---")
        # Assuming table 1 has capacity 2
        booking_too_many = book_table(table_id=1, guest_name="Crowd", num_guests=5, datetime_str="2024-08-15 20:00:00")
        print(f"Booking with too many guests: {booking_too_many}")


        print("\n--- Testing view_menu ---")
        menu = view_menu()
        if menu:
            print(f"Found {len(menu)} menu items:")
            for item in menu:
                print(item)
        else:
            print("No menu items found or error.")

        print("\n--- Testing cancel_reservation (non-existent) ---")
        cancel_non_existent = cancel_reservation(99999)
        print(f"Cancel non-existent reservation result: {cancel_non_existent}")
    
    print("\nBasic tests complete.")
