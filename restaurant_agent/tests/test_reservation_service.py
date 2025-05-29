import unittest
from unittest.mock import patch
import os
import sqlite3
from ..core_logic import reservation_service
from ..core_logic import db_manager # Will be patched

# Determine paths
TEST_DIR = os.path.dirname(__file__)
SCHEMA_PATH = os.path.abspath(os.path.join(TEST_DIR, '..', 'database', 'schema.sql'))

class TestReservationService(unittest.TestCase):

    def setUp(self):
        """Set up a temporary database and patch DB_PATH."""
        self.test_db_filename = "test_restaurant_temp.db"
        # In case a previous test run failed and didn't clean up
        if os.path.exists(self.test_db_filename):
            os.remove(self.test_db_filename)

        # Patch db_manager.DB_PATH to use our temporary database file
        self.patcher = patch('restaurant_agent.core_logic.db_manager.DB_PATH', self.test_db_filename)
        self.mock_db_path = self.patcher.start()

        self.conn = sqlite3.connect(self.test_db_filename)
        self.conn.row_factory = sqlite3.Row
        
        # Create schema
        if not os.path.exists(SCHEMA_PATH):
            raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}. Ensure path is correct.")
        with open(SCHEMA_PATH, 'r') as f:
            schema_sql = f.read()
        self.conn.executescript(schema_sql)

        # Populate with initial data
        cursor = self.conn.cursor()
        # Tables: (id, table_number, capacity)
        cursor.execute("INSERT INTO tables (id, table_number, capacity) VALUES (?, ?, ?)", (1, 101, 2))
        cursor.execute("INSERT INTO tables (id, table_number, capacity) VALUES (?, ?, ?)", (2, 102, 4))
        cursor.execute("INSERT INTO tables (id, table_number, capacity) VALUES (?, ?, ?)", (3, 103, 4))
        
        # Menu items: (name, category, price)
        cursor.execute("INSERT INTO menu_items (name, category, price) VALUES (?, ?, ?)", ('Test Pizza', 'food', 10.99))
        cursor.execute("INSERT INTO menu_items (name, category, price) VALUES (?, ?, ?)", ('Test Cola', 'drink', 1.99))
        
        # Initial reservation for Table 3 (ID 3)
        cursor.execute("INSERT INTO reservations (table_id, guest_name, num_guests, reservation_time) VALUES (?, ?, ?, ?)",
                       (3, "Initial Booker", 2, "2024-01-01 18:00:00"))
        self.conn.commit()

    def tearDown(self):
        """Stop the patcher, close connection, and remove the temporary database."""
        self.conn.close()
        self.patcher.stop()
        if os.path.exists(self.test_db_filename):
            os.remove(self.test_db_filename)

    def test_view_menu(self):
        menu = reservation_service.view_menu()
        self.assertEqual(len(menu), 2)
        self.assertTrue(any(item['name'] == 'Test Pizza' for item in menu))
        self.assertTrue(any(item['name'] == 'Test Cola' for item in menu))

    def test_find_available_tables_success(self):
        # Initial state: Table 3 (ID 3, cap 4) is booked at "2024-01-01 18:00:00".
        # For num_guests=2 at "2024-01-01 19:00:00":
        # Table 1 (ID 1, cap 2) - available
        # Table 2 (ID 2, cap 4) - available
        # Table 3 (ID 3, cap 4) - available (booked at a different time)
        available = reservation_service.find_available_tables(num_guests=2, datetime_str="2024-01-01 19:00:00")
        self.assertIsNotNone(available)
        self.assertEqual(len(available), 3) # Tables 1, 2, and 3
        table_ids = {t['table_id'] for t in available}
        self.assertIn(1, table_ids)
        self.assertIn(2, table_ids)
        self.assertIn(3, table_ids)

    def test_find_available_tables_exact_capacity(self):
        # For num_guests=4 at "2024-01-01 19:00:00":
        # Table 1 (ID 1, cap 2) - not enough capacity
        # Table 2 (ID 2, cap 4) - available
        # Table 3 (ID 3, cap 4) - available (booked at a different time)
        available = reservation_service.find_available_tables(num_guests=4, datetime_str="2024-01-01 19:00:00")
        self.assertIsNotNone(available)
        self.assertEqual(len(available), 2) # Tables 2 and 3
        table_ids = {t['table_id'] for t in available}
        self.assertIn(2, table_ids)
        self.assertIn(3, table_ids)
        # Order by capacity is in service, if same capacity, order is by DB (likely ID).
        # To make it robust, we check for presence, not specific order for items with same capacity.


    def test_find_available_tables_no_capacity(self):
        available = reservation_service.find_available_tables(num_guests=10, datetime_str="2024-01-01 19:00:00")
        self.assertEqual(len(available), 0)

    def test_find_available_tables_all_booked_or_insufficient_at_time(self):
        # Table 3 (ID 3, cap 4) is booked at 2024-01-01 18:00:00 by setUp
        # Let's book Table 2 (ID 2, cap 4) at the same time
        reservation_service.book_table(table_id=2, guest_name="Booker Two", num_guests=3, datetime_str="2024-01-01 18:00:00")
        
        # Now, find tables for 2 guests at 2024-01-01 18:00:00
        # Table 1 (cap 2) should be the only one available.
        available = reservation_service.find_available_tables(num_guests=2, datetime_str="2024-01-01 18:00:00")
        self.assertEqual(len(available), 1)
        self.assertEqual(available[0]['table_id'], 1)

        # Book table 1 as well
        reservation_service.book_table(table_id=1, guest_name="Booker One", num_guests=1, datetime_str="2024-01-01 18:00:00")
        available_again = reservation_service.find_available_tables(num_guests=2, datetime_str="2024-01-01 18:00:00")
        self.assertEqual(len(available_again), 0)


    def test_book_table_success(self):
        result = reservation_service.book_table(table_id=1, guest_name="Test Guest", num_guests=2, datetime_str="2024-01-01 20:00:00")
        self.assertTrue(result['success'])
        self.assertIn('reservation_id', result)
        reservation_id = result['reservation_id']
        
        # Verify in DB
        details = reservation_service.get_reservation_details(reservation_id)
        self.assertIsNotNone(details)
        self.assertEqual(details['guest_name'], "Test Guest")
        self.assertEqual(details['table_number'], 101) # Table 1 has number 101

    def test_book_table_fail_no_capacity(self):
        # Table 1 (ID 1) has capacity 2
        result = reservation_service.book_table(table_id=1, guest_name="Too Many", num_guests=3, datetime_str="2024-01-01 20:00:00")
        self.assertFalse(result['success'])
        self.assertIn("exceeds table capacity", result['message'])

    def test_book_table_fail_already_booked(self):
        # Book Table 1 at 2024-01-01 21:00:00
        reservation_service.book_table(table_id=1, guest_name="First Booker", num_guests=1, datetime_str="2024-01-01 21:00:00")
        
        # Attempt to book again
        result = reservation_service.book_table(table_id=1, guest_name="Second Booker", num_guests=1, datetime_str="2024-01-01 21:00:00")
        self.assertFalse(result['success'])
        self.assertIn("already booked", result['message'])

    def test_book_table_fail_non_existent_table(self):
        result = reservation_service.book_table(table_id=999, guest_name="Ghost Guest", num_guests=1, datetime_str="2024-01-01 20:00:00")
        self.assertFalse(result['success'])
        self.assertIn("Table not found", result['message'])


    def test_cancel_reservation_success(self):
        # Book a table first
        booking = reservation_service.book_table(table_id=1, guest_name="To Be Cancelled", num_guests=1, datetime_str="2024-01-01 22:00:00")
        self.assertTrue(booking['success'])
        reservation_id = booking['reservation_id']
        
        cancel_result = reservation_service.cancel_reservation(reservation_id)
        self.assertTrue(cancel_result['success'])
        self.assertEqual(cancel_result['message'], "Reservation cancelled successfully.")
        
        # Verify it's gone
        details_after_cancel = reservation_service.get_reservation_details(reservation_id)
        self.assertIsNone(details_after_cancel)

    def test_cancel_reservation_fail_not_found(self):
        result = reservation_service.cancel_reservation(reservation_id=999) # Non-existent ID
        self.assertFalse(result['success'])
        self.assertEqual(result['message'], "Reservation not found.")

    def test_get_reservation_details_success(self):
        # Book a table first
        booking = reservation_service.book_table(table_id=2, guest_name="Detail Guest", num_guests=3, datetime_str="2024-01-01 23:00:00")
        self.assertTrue(booking['success'])
        reservation_id = booking['reservation_id']
        
        details = reservation_service.get_reservation_details(reservation_id)
        self.assertIsNotNone(details)
        self.assertEqual(details['id'], reservation_id)
        self.assertEqual(details['guest_name'], "Detail Guest")
        self.assertEqual(details['num_guests'], 3)
        self.assertEqual(details['table_number'], 102) # Table 2 has number 102
        self.assertEqual(details['table_capacity'], 4)

    def test_get_reservation_details_not_found(self):
        details = reservation_service.get_reservation_details(reservation_id=999) # Non-existent ID
        self.assertIsNone(details)

if __name__ == '__main__':
    unittest.main()
