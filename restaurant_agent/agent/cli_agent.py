import os
from ..core_logic import db_manager # For DB_PATH existence check
from .restaurant_agent import RestaurantAgent # New import

def main():
    """Main function to run the CLI testing interface for RestaurantAgent."""
    # 1. Database Existence Check
    if not os.path.exists(db_manager.DB_PATH):
        print(f"Database file not found at {db_manager.DB_PATH}")
        print("Please set up the database first by running:")
        print("  python -m restaurant_agent.database.setup_db")
        return

    # 2. Instantiate RestaurantAgent
    print("Initializing Restaurant Agent...")
    agent = RestaurantAgent()

    # 3. Check Agent (GemmaService) Initialization
    if not agent.gemma_service or not agent.gemma_service.initialized:
        print("\nCRITICAL: Restaurant Agent's NLU service (Gemma) could not be initialized.")
        print("Please check the Gemma model setup, configuration, and logs.")
        print("The agent cannot function without its NLU capabilities. Exiting.")
        return

    # 4. Welcome Message & Loop
    print("\nRestaurant Agent (Gemma-powered) is ready. Type 'exit' to quit.")
    print("You can interact with the agent using natural language.")
    print("Example: 'Hello', 'Show menu', 'Book a table for 2 tomorrow at 7pm', 'My name is Alex'")
    print("-" * 50)

    while True:
        try:
            user_input = input("You: ")
            if user_input.strip().lower() == 'exit':
                # Let the agent handle the "exit" message if it has specific goodbye logic
                response = agent.handle_message(user_input)
                print(f"Agent: {response}")
                print("Exiting CLI.")
                break
            
            response = agent.handle_message(user_input)
            print(f"Agent: {response}")
            print("-" * 30) # Separator for readability

        except KeyboardInterrupt:
            print("\nExiting CLI via KeyboardInterrupt.")
            # Optionally, send a "goodbye" or cleanup message to agent if needed
            # agent.handle_message("exit") # or a specific cleanup method
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred in the CLI: {e}")
            # Log the error, and potentially try to recover or exit gracefully
            break # For now, exit on unexpected errors

if __name__ == '__main__':
    # This allows running the CLI using: python -m restaurant_agent.agent.cli_agent
    # Ensure that the restaurant_agent package is in PYTHONPATH or you are in the directory above restaurant_agent
    main()
