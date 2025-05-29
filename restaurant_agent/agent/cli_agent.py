import os
from ..core_logic import reservation_service
from ..core_logic import db_manager # To access DB_PATH for check

def handle_view_menu():
    """Handles viewing the menu."""
    print("\n--- Menu ---")
    menu_items = reservation_service.view_menu()
    if not menu_items:
        print("The menu is currently empty or there was an error retrieving it.")
        return
    
    foods = [item for item in menu_items if item['category'] == 'food']
    drinks = [item for item in menu_items if item['category'] == 'drink']

    if foods:
        print("\n-- Food --")
        for item in foods:
            print(f"  ID: {item['id']}, Name: {item['name']}, Price: ${item['price']:.2f}")
    
    if drinks:
        print("\n-- Drinks --")
        for item in drinks:
            print(f"  ID: {item['id']}, Name: {item['name']}, Price: ${item['price']:.2f}")
    print("------------")

def handle_find_tables():
    """Handles finding available tables."""
    print("\n--- Find Available Tables ---")
    try:
        num_guests_str = input("Enter number of guests: ")
        num_guests = int(num_guests_str)
        if num_guests <= 0:
            print("Number of guests must be a positive integer.")
            return
    except ValueError:
        print("Invalid input for number of guests. Please enter a number.")
        return

    datetime_str = input("Enter desired date and time (YYYY-MM-DD HH:MM:SS): ")
    # Basic validation for datetime format could be added here if desired
    # For now, we rely on the service/DB to handle invalid formats if necessary

    available_tables = reservation_service.find_available_tables(num_guests, datetime_str)
    if not available_tables:
        print(f"No tables found for {num_guests} guests at {datetime_str}, or an error occurred.")
    else:
        print("\nAvailable Tables:")
        for table in available_tables:
            print(f"  Table ID: {table['table_id']}, Number: {table['table_number']}, Capacity: {table['capacity']}")
    print("---------------------------")

def handle_book_table():
    """Handles booking a table."""
    print("\n--- Book a Table ---")
    try:
        table_id_str = input("Enter Table ID to book: ")
        table_id = int(table_id_str)
    except ValueError:
        print("Invalid Table ID. Please enter a number.")
        return

    guest_name = input("Enter your name: ")
    if not guest_name.strip():
        print("Guest name cannot be empty.")
        return
        
    try:
        num_guests_str = input("Enter number of guests: ")
        num_guests = int(num_guests_str)
        if num_guests <= 0:
            print("Number of guests must be a positive integer.")
            return
    except ValueError:
        print("Invalid input for number of guests. Please enter a number.")
        return

    datetime_str = input("Enter desired date and time (YYYY-MM-DD HH:MM:SS): ")

    result = reservation_service.book_table(table_id, guest_name, num_guests, datetime_str)
    if result.get('success'):
        print(f"Success! {result.get('message')} Reservation ID: {result.get('reservation_id')}")
    else:
        print(f"Failed to book table. Reason: {result.get('message')}")
    print("--------------------")

def handle_view_reservation_details():
    """Handles viewing reservation details."""
    print("\n--- View Reservation Details ---")
    try:
        reservation_id_str = input("Enter your Reservation ID: ")
        reservation_id = int(reservation_id_str)
    except ValueError:
        print("Invalid Reservation ID. Please enter a number.")
        return

    details = reservation_service.get_reservation_details(reservation_id)
    if not details:
        print(f"No reservation found with ID {reservation_id}, or an error occurred.")
    else:
        print("\nReservation Details:")
        print(f"  ID: {details['id']}")
        print(f"  Guest Name: {details['guest_name']}")
        print(f"  Number of Guests: {details['num_guests']}")
        print(f"  Time: {details['reservation_time']}")
        print(f"  Table Number: {details['table_number']}")
        print(f"  Table Capacity: {details['table_capacity']}")
    print("------------------------------")

def handle_cancel_reservation():
    """Handles cancelling a reservation."""
    print("\n--- Cancel Reservation ---")
    try:
        reservation_id_str = input("Enter Reservation ID to cancel: ")
        reservation_id = int(reservation_id_str)
    except ValueError:
        print("Invalid Reservation ID. Please enter a number.")
        return

    result = reservation_service.cancel_reservation(reservation_id)
    if result.get('success'):
        print(f"Success! {result.get('message')}")
    else:
        print(f"Failed to cancel reservation. Reason: {result.get('message')}")
    print("------------------------")

def main():
    """Main function to run the CLI agent."""
    if not os.path.exists(db_manager.DB_PATH):
        print(f"Database file not found at {db_manager.DB_PATH}")
        print("Please set up the database first by running:")
        print("  python -m restaurant_agent.database.setup_db")
        return

    while True:
        print("\nRestaurant Reservation Agent")
        print("1. View Menu")
        print("2. Find Available Tables")
        print("3. Book a Table")
        print("4. View Reservation Details")
        print("5. Cancel Reservation")
        print("6. Exit")

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            handle_view_menu()
        elif choice == '2':
            handle_find_tables()
        elif choice == '3':
            handle_book_table()
        elif choice == '4':
            handle_view_reservation_details()
        elif choice == '5':
            handle_cancel_reservation()
        elif choice == '6':
            print("Exiting. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 6.")

if __name__ == '__main__':
    # This allows running the CLI using: python -m restaurant_agent.agent.cli_agent
    # Ensure that the restaurant_agent package is in PYTHONPATH or you are in the directory above restaurant_agent
    main()
