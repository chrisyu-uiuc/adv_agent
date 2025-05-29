# Requires: pip install python-dateutil
import json
from datetime import datetime
try:
    from dateutil import parser as dateutil_parser
except ImportError:
    print("Warning: python-dateutil not found. Date/time parsing will be basic.")
    dateutil_parser = None

from .gemma_service import GemmaService
from ..core_logic import reservation_service
from ..core_logic.db_manager import DB_PATH # Direct use of DB_PATH for service functions

class RestaurantAgent:
    def __init__(self):
        """
        Initializes the RestaurantAgent.
        """
        self.gemma_service = GemmaService() # Consider passing model_name if needed
        self.gemma_service.initialize_gemma()
        
        if not self.gemma_service.initialized:
            print("CRITICAL: GemmaService failed to initialize. Agent may not be operational.")
            # Depending on desired behavior, could raise an error or set an error state
            
        self.db_path = DB_PATH # Service functions might not need this if they internally use db_manager
                              # For now, assuming they might, or for consistency.
                              # The reservation_service functions currently get connection internally
                              # and don't take db_path. This can be removed if service functions don't need it.

        self.conversation_state = {} # To store intent_in_progress, collected_entities, missing_entities

    def _normalize_datetime(self, datetime_str: str) -> str | None:
        """
        Parses natural language date/time strings into "YYYY-MM-DD HH:MM:SS" format.
        """
        if not dateutil_parser:
            print("Warning: dateutil.parser not available. Datetime normalization will be skipped.")
            # Basic pass-through or very simple heuristic if dateutil is missing
            if isinstance(datetime_str, str) and len(datetime_str) > 5: # Arbitrary basic check
                 # Attempt to see if it's already somewhat formatted (very naive)
                try:
                    # Example: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD HH:MM
                    datetime.strptime(datetime_str.split()[0], "%Y-%m-%d")
                    return datetime_str 
                except ValueError:
                    return None # Cannot parse simply
            return None

        if not datetime_str or not isinstance(datetime_str, str):
            return None
        try:
            # Heuristic: if it's just "tonight", "tomorrow", add a default time like 7 PM
            # dateutil can parse "tomorrow 7pm" but "tomorrow" alone might be just the date.
            # This is a simple addition; more robust handling might be needed.
            if datetime_str.lower() in ["today", "tonight"]:
                dt = dateutil_parser.parse(datetime_str)
                dt = dt.replace(hour=19, minute=0, second=0, microsecond=0) # Default to 7 PM
            elif datetime_str.lower() == "tomorrow":
                dt = dateutil_parser.parse(datetime_str)
                dt = dt.replace(hour=19, minute=0, second=0, microsecond=0) # Default to 7 PM for tomorrow
            else:
                dt = dateutil_parser.parse(datetime_str)
            
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (dateutil_parser.ParserError, TypeError, ValueError) as e:
            print(f"Error parsing datetime string '{datetime_str}': {e}")
            return None

    def _format_menu(self, menu_items_list: list) -> str:
        if not menu_items_list:
            return "The menu is currently empty or there was an error retrieving it."
        
        response = "Here's our menu:\n"
        foods = [item for item in menu_items_list if item['category'] == 'food']
        drinks = [item for item in menu_items_list if item['category'] == 'drink']

        if foods:
            response += "\n-- Food --\n"
            for item in foods:
                response += f"  - {item['name']}: ${item['price']:.2f}\n"
        
        if drinks:
            response += "\n-- Drinks --\n"
            for item in drinks:
                response += f"  - {item['name']}: ${item['price']:.2f}\n"
        return response

    def _format_available_tables(self, tables_list: list) -> str:
        if not tables_list:
            return "Sorry, no tables match that criteria right now."
        response = "Here are the available tables:\n"
        for table in tables_list:
            response += f"  - Table ID: {table['table_id']} (Number: {table['table_number']}, Capacity: {table['capacity']})\n"
        return response

    def _reset_conversation_state(self):
        print("State: Resetting conversation state.")
        self.conversation_state = {}

    def handle_message(self, user_message: str) -> str:
        if not self.gemma_service.initialized:
            return "I'm sorry, my brain (NLU service) isn't working right now. Please try again later."

        nlu_result = self.gemma_service.process_user_input(user_message)
        intent = nlu_result.get('intent', 'error')
        entities = nlu_result.get('entities', {})
        
        print(f"NLU Result: Intent='{intent}', Entities={json.dumps(entities)}, State before: {json.dumps(self.conversation_state)}")

        # Handle ongoing multi-turn intents first
        current_task = self.conversation_state.get('intent_in_progress')

        if current_task == 'book_table':
            # Update collected entities
            self.conversation_state['collected_entities'].update(entities)
            
            # Normalize datetime if provided
            if 'datetime_str' in self.conversation_state['collected_entities'] and \
               not self.conversation_state['collected_entities'].get('datetime_str_normalized'):
                norm_dt = self._normalize_datetime(self.conversation_state['collected_entities']['datetime_str'])
                if norm_dt:
                    self.conversation_state['collected_entities']['datetime_str_normalized'] = norm_dt
                    if 'datetime_str' in self.conversation_state.get('missing_entities', []):
                        self.conversation_state['missing_entities'].remove('datetime_str')
                else:
                    # Failed to parse new datetime, keep it as missing or re-add
                    if 'datetime_str' not in self.conversation_state.get('missing_entities', []):
                         self.conversation_state.setdefault('missing_entities', []).append('datetime_str')
                    return f"I had trouble understanding the date and time: '{self.conversation_state['collected_entities']['datetime_str']}'. Could you please clarify?"

            # Check for missing entities based on the list
            if 'num_guests' not in self.conversation_state['collected_entities'] and \
               'num_guests' in self.conversation_state.get('missing_entities', []):
                if isinstance(entities.get('num_guests'), int) and entities['num_guests'] > 0:
                     self.conversation_state['collected_entities']['num_guests'] = entities['num_guests']
                     self.conversation_state['missing_entities'].remove('num_guests')
                # If intent is provide_information and info_topic is num_guests
                elif intent == 'provide_information' and entities.get('info_topic') == 'num_guests':
                    try:
                        num_g = int(entities.get('info_value'))
                        if num_g > 0:
                            self.conversation_state['collected_entities']['num_guests'] = num_g
                            if 'num_guests' in self.conversation_state.get('missing_entities', []):
                                self.conversation_state['missing_entities'].remove('num_guests')
                        else:
                            return "Number of guests must be positive. How many guests?"
                    except (ValueError, TypeError):
                        return "That doesn't seem like a valid number for guests. How many guests?"
                # else: still missing

            if 'guest_name' not in self.conversation_state['collected_entities'] and \
               'guest_name' in self.conversation_state.get('missing_entities', []):
                if entities.get('guest_name'):
                    self.conversation_state['collected_entities']['guest_name'] = entities['guest_name']
                    self.conversation_state['missing_entities'].remove('guest_name')
                elif intent == 'provide_information' and entities.get('info_topic') == 'guest_name' and entities.get('info_value'):
                    self.conversation_state['collected_entities']['guest_name'] = entities.get('info_value')
                    if 'guest_name' in self.conversation_state.get('missing_entities', []):
                        self.conversation_state['missing_entities'].remove('guest_name')
                # else: still missing

            # Re-check missing entities
            self.conversation_state['missing_entities'] = [
                e for e in ['num_guests', 'datetime_str', 'guest_name'] 
                if e == 'datetime_str' and not self.conversation_state['collected_entities'].get('datetime_str_normalized')
                or e != 'datetime_str' and not self.conversation_state['collected_entities'].get(e)
            ]
            # Remove 'guest_name' from missing if we haven't even presented tables yet
            if not self.conversation_state.get('tables_found_for_booking'):
                 if 'guest_name' in self.conversation_state['missing_entities']:
                    self.conversation_state['missing_entities'].remove('guest_name')


            if 'num_guests' in self.conversation_state['missing_entities']:
                return "How many guests will that be?"
            if 'datetime_str' in self.conversation_state['missing_entities']: # This means datetime_str_normalized is missing
                return "What date and time are you looking for?"

            # All primary details (guests, time) collected, find tables
            num_guests = self.conversation_state['collected_entities']['num_guests']
            datetime_str_norm = self.conversation_state['collected_entities']['datetime_str_normalized']

            if not self.conversation_state.get('tables_found_for_booking'):
                available_tables = reservation_service.find_available_tables(num_guests, datetime_str_norm)
                if available_tables:
                    self.conversation_state['tables_found_for_booking'] = available_tables
                    # Simplified: pick first table for now.
                    self.conversation_state['selected_table_id'] = available_tables[0]['table_id'] 
                    # Now ask for guest_name if missing
                    if 'guest_name' not in self.conversation_state['collected_entities']:
                        self.conversation_state.setdefault('missing_entities', []).append('guest_name')
                        return f"Great! I found a table (ID {available_tables[0]['table_id']}, Capacity {available_tables[0]['capacity']}). What name should I make the reservation under?"
                else:
                    self._reset_conversation_state()
                    return f"Sorry, no tables are available for {num_guests} guests on {datetime_str_norm}."

            # If tables were found and we are here, means we might be waiting for guest_name or confirmation
            if 'guest_name' in self.conversation_state.get('missing_entities', []):
                 return "What name should I make the reservation under?"

            # All details collected (num_guests, datetime_str_norm, guest_name, selected_table_id)
            if self.conversation_state.get('selected_table_id') and \
               self.conversation_state['collected_entities'].get('guest_name'):
                
                table_id = self.conversation_state['selected_table_id']
                guest_name = self.conversation_state['collected_entities']['guest_name']
                
                # Confirmation step (simplified)
                if intent == 'affirm' or not self.conversation_state.get('confirmation_pending'):
                    print(f"State: Attempting to book table {table_id} for {guest_name}, {num_guests} guests at {datetime_str_norm}")
                    booking_result = reservation_service.book_table(
                        table_id, guest_name, num_guests, datetime_str_norm
                    )
                    self._reset_conversation_state()
                    if booking_result['success']:
                        return f"Successfully booked! Your reservation ID is {booking_result['reservation_id']}."
                    else:
                        return f"Booking failed: {booking_result['message']}"
                elif intent == 'deny':
                    response = "Okay, I won't book that table. Let me know if there's anything else."
                    self._reset_conversation_state()
                    return response
                else: # Waiting for affirm/deny or more info
                    self.conversation_state['confirmation_pending'] = True
                    return f"Okay, I have table {table_id} for {num_guests} guests at {datetime_str_norm} under the name {guest_name}. Should I confirm this booking? (yes/no)"
            # Fall through if some logic error in state

        # --- Intent-based handling for new interactions ---
        if intent == 'greet':
            return "Hello! How can I help you today? You can ask to view the menu, book a table, or cancel a reservation."
        
        elif intent == 'goodbye':
            self._reset_conversation_state()
            return "Goodbye! Hope to see you soon."

        elif intent == 'query_menu':
            menu_items = reservation_service.view_menu()
            return self._format_menu(menu_items)

        elif intent == 'query_table_availability':
            num_guests = entities.get('num_guests')
            datetime_str_raw = entities.get('datetime_str')
            
            if not num_guests or not datetime_str_raw:
                # Start a book_table flow to collect missing info
                self.conversation_state = {
                    'intent_in_progress': 'book_table', # Treat as start of booking
                    'collected_entities': entities,
                    'missing_entities': []
                }
                if not num_guests: self.conversation_state['missing_entities'].append('num_guests')
                if not datetime_str_raw: self.conversation_state['missing_entities'].append('datetime_str')
                
                response = "Sure, I can check availability. "
                if not num_guests: response += "How many guests?"
                elif not datetime_str_raw: response += "For what date and time?"
                return response

            datetime_str_norm = self._normalize_datetime(datetime_str_raw)
            if not datetime_str_norm:
                return f"I had trouble understanding the date and time: '{datetime_str_raw}'. Could you please clarify?"

            available_tables = reservation_service.find_available_tables(num_guests, datetime_str_norm)
            self._reset_conversation_state() # This is a one-shot query
            return self._format_available_tables(available_tables)
            
        elif intent == 'book_table':
            self.conversation_state = {
                'intent_in_progress': 'book_table',
                'collected_entities': entities, # Start with NLU extracted entities
                'missing_entities': [],
                'tables_found_for_booking': None, # Store tables once found
                'selected_table_id': None,
                'confirmation_pending': False
            }
            
            # Normalize datetime immediately if provided
            if 'datetime_str' in entities:
                norm_dt = self._normalize_datetime(entities['datetime_str'])
                if norm_dt:
                    self.conversation_state['collected_entities']['datetime_str_normalized'] = norm_dt
                else:
                    self.conversation_state['missing_entities'].append('datetime_str') # Mark as missing if parsing fails
            else:
                 self.conversation_state['missing_entities'].append('datetime_str')

            if not entities.get('num_guests'): self.conversation_state['missing_entities'].append('num_guests')
            # guest_name is asked after tables are found and selected

            # Ask for the first missing piece of information for finding tables
            if 'num_guests' in self.conversation_state['missing_entities']:
                return "Sure, I can help with that. How many guests will it be?"
            if 'datetime_str' in self.conversation_state['missing_entities']: # Implies normalization failed or not provided
                return "Okay, for what date and time are you looking to book?"
            
            # If num_guests and datetime_str (normalized) are already present from NLU
            # (e.g. "book a table for 2 for tomorrow at 7pm")
            # This will be handled by the next turn's 'book_table' ongoing logic
            return self.handle_message(user_message) # Re-process with state set

        elif intent == 'cancel_reservation':
            reservation_id = entities.get('reservation_id')
            if not reservation_id and intent == 'provide_information' and entities.get('info_topic') == 'reservation_id':
                reservation_id = entities.get('info_value')

            if reservation_id:
                # Attempt to convert to int if it's a string of digits, service might expect int
                try:
                    res_id_int = int(reservation_id)
                    cancel_result = reservation_service.cancel_reservation(res_id_int)
                except ValueError: # If reservation_id is not purely numeric, pass as is if service handles it
                    cancel_result = reservation_service.cancel_reservation(str(reservation_id)) # Assuming service can handle string IDs if needed

                self._reset_conversation_state()
                if cancel_result['success']:
                    return f"Reservation {reservation_id} cancelled successfully."
                else:
                    return f"Failed to cancel reservation {reservation_id}: {cancel_result['message']}"
            else:
                # TODO: Could set conversation_state to wait for reservation_id
                return "Okay, what is the reservation ID you'd like to cancel?"

        elif intent == 'affirm':
            if current_task == 'book_table' and self.conversation_state.get('confirmation_pending'):
                # Re-enter the booking logic, it should now proceed with booking
                self.conversation_state['confirmation_pending'] = False # Clear the flag
                # We need to pass a message that represents the ongoing interaction,
                # or directly call a part of the booking logic.
                # For simplicity, let's re-trigger with a generic "yes" to use existing paths.
                return self.handle_message("yes") 
            return "Okay!"

        elif intent == 'deny':
            if current_task == 'book_table' and self.conversation_state.get('confirmation_pending'):
                self.conversation_state['confirmation_pending'] = False
                response = "Okay, I won't proceed with that. What would you like to do instead?"
                self._reset_conversation_state()
                return response
            return "Okay, understood."
            
        elif intent == 'provide_information':
            # This is generally handled within the context of an ongoing intent (e.g. book_table)
            # If it's out of context, it's like chit-chat or error
            if current_task: # If there's an ongoing task, let that task's logic handle it (already done above)
                 return self.handle_message(user_message) # Re-process in context
            return f"Thanks for the information: {entities.get('info_topic', 'something')} is {entities.get('info_value', 'not clear')}."


        # Fallback for unhandled intents or errors
        error_message = nlu_result.get('message', "I'm not sure how to help with that.")
        if intent == 'error' and 'raw_output' in nlu_result: # NLU parsing error
             print(f"NLU parsing error, raw output: {nlu_result['raw_output']}")
             # Don't expose raw output to user
             return "I'm having a bit of trouble understanding. Could you try rephrasing?"
        
        # Default response for intents not specifically handled above
        self._reset_conversation_state() # Reset state if we don't know what to do
        return f"I'm not quite sure about '{intent}'. I can help with viewing the menu, booking tables, or cancelling reservations."


if __name__ == '__main__':
    agent = RestaurantAgent()
    if not agent.gemma_service.initialized:
        print("Agent's NLU service could not be initialized. Exiting.")
    else:
        print("\nRestaurant Agent is ready. Type 'exit' to quit.")
        print("Example queries:")
        print(" - 'Hello'")
        print(" - 'Show me the menu'")
        print(" - 'Book a table'")
        print(" - 'I need a table for 3 people for tomorrow at 7pm'")
        print(" - 'Cancel reservation 123'")
        print("-" * 30)

        while True:
            user_in = input("You: ")
            if user_in.lower() == 'exit':
                response = agent.handle_message(user_in) # Let agent handle 'goodbye' intent
                print(f"Agent: {response}")
                break
            
            response = agent.handle_message(user_in)
            print(f"Agent: {response}")
            # For debugging, print state after each turn
            # print(f"DEBUG: State after agent response: {json.dumps(agent.conversation_state, indent=2)}")
            print("-" * 30)
