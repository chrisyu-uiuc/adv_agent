import json
import re

# Potential imports - these might change based on the specific Gemma access method
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
except ImportError:
    print("Warning: torch or transformers not found. GemmaService will not be functional.")
    torch = None
    AutoTokenizer = None
    AutoModelForCausalLM = None

class GemmaService:
    # Default model: "google/gemma-2b" is a common small variant.
    # "google/gemma-1b" is not a standard Hugging Face identifier for a base model;
    # typically, Gemma models are named like "gemma-2b", "gemma-7b", or specific fine-tunes.
    # Users can override model_name when instantiating GemmaService.
    def __init__(self, model_name: str = "google/gemma-2b"):
        """
        Initializes the GemmaService.
        """
        self.tokenizer = None
        self.model = None
        self.initialized = False
        
        self.model_name = model_name
        
        if torch:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            # Attempt to use bfloat16 if available on CUDA for better performance/memory
            self.torch_dtype = torch.bfloat16 if self.device == "cuda" and torch.cuda.is_bf16_supported() else torch.float16
        else:
            self.device = "cpu"
            self.torch_dtype = torch.float32 # Default for CPU or if torch not fully functional

        print(f"GemmaService configured for model: {self.model_name}, device: {self.device}, dtype: {self.torch_dtype}")

    def initialize_gemma(self):
        """
        Loads the Gemma tokenizer and model from Hugging Face.
        """
        if not torch or not AutoTokenizer or not AutoModelForCausalLM:
            print("Error: Required libraries (torch, transformers) are not available.")
            print("Gemma LLM cannot be initialized.")
            self.initialized = False
            return

        if self.initialized:
            print(f"Gemma service ({self.model_name}) already initialized.")
            return

        print(f"Initializing Gemma LLM: {self.model_name} on {self.device} with dtype {self.torch_dtype}...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            # For smaller models like gemma-2b, device_map="auto" or specific device might be fine.
            # If OOM errors occur, device_map="auto" with accelerate or more advanced sharding is needed.
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=self.torch_dtype,
                device_map=self.device 
            )
            self.model.eval() # Set the model to evaluation mode
            self.initialized = True
            print(f"Gemma LLM ({self.model_name}) initialized successfully on {self.device}.")
        except Exception as e:
            print(f"Error during Gemma LLM initialization for model {self.model_name}: {e}")
            self.tokenizer = None
            self.model = None
            self.initialized = False

    def generate_text(self, prompt: str, max_new_tokens: int = 200) -> str:
        """
        Generates text using the loaded Gemma model.
        
        Args:
            prompt: The input text prompt.
            max_new_tokens: The maximum number of new tokens to generate.
            
        Returns:
            The generated text as a string.
        """
        if not self.initialized:
            print("Gemma service not initialized. Attempting to initialize now...")
            self.initialize_gemma()
            if not self.initialized: # If initialization failed
                return "Error: Gemma service could not be initialized. Cannot generate text."

        if not self.model or not self.tokenizer:
             return "Error: Model or tokenizer not available even after initialization attempt."

        print(f"\nGenerating text for prompt (first 80 chars): '{prompt[:80]}...'")
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt", padding=True, truncation=True).to(self.device)
            
            with torch.no_grad(): # Ensure no gradients are computed during inference
                outputs = self.model.generate(
                    input_ids=inputs.input_ids,
                    attention_mask=inputs.attention_mask,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,      # Enable sampling
                    temperature=0.6,   # Controls randomness: lower means more deterministic
                    top_p=0.9,         # Nucleus sampling: selects from tokens comprising top P% probability mass
                    top_k=50,          # Selects from top K most likely tokens
                    pad_token_id=self.tokenizer.eos_token_id # Important for open-ended generation
                )
            
            # outputs[0] typically contains the full sequence (prompt + generation) for single return sequence
            # We need to decode only the generated part if the prompt is included in the output
            # For many models, the output of generate includes the input_ids.
            # Slicing the output tokens: outputs[0][inputs.input_ids.shape[-1]:]
            # However, some models/settings might only return new tokens.
            # tokenizer.decode(outputs[0]) usually handles this correctly for from_pretrained models.
            # For safety, let's decode the whole sequence and then optionally strip the prompt if present.
            
            full_generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove the input prompt from the generated text if it's prepended
            if full_generated_text.startswith(prompt):
                 generated_text = full_generated_text[len(prompt):].strip()
            else:
                # Fallback for cases where the model might not prepend the exact prompt
                # or if the prompt is implicitly handled by the model's generation process.
                # This part might need adjustment based on observed model behavior.
                # A common pattern is that the generation starts right after the prompt.
                # If the tokenizer is adding BOS tokens, they might also be part of the output.
                # For now, we assume the decode handles this.
                # If the prompt itself is part of the generation (e.g. chat models),
                # then we want the full_generated_text minus the initial prompt.
                # Let's try to find the start of the actual response if the prompt is complex.
                # The most robust way is to check if outputs[0] starts with inputs.input_ids
                # and slice the token tensor before decoding.
                
                # Simpler approach for now: if the prompt is simple, direct slicing works.
                # If the prompt is part of a template, the model's output might be just the completion.
                # The current setup is for the model to complete the prompt "Assistant: <JSON_Output>"
                # So, the `full_generated_text` should be what we need.
                generated_text = full_generated_text # Assuming the prompt leads to the desired JSON output

            print(f"Gemma generated (raw): '{generated_text}'")
            return generated_text
        except Exception as e:
            print(f"Error during Gemma text generation: {e}")
            return "Error generating text."

    def _parse_datetime_entities(self, entities: dict) -> dict:
        """
        Parses datetime strings in entities into a standard format.
        Placeholder: Uses simple heuristics. Consider using dateutil.parser for robust parsing.
        `pip install python-dateutil` would be needed for that.
        """
        if 'datetime_str' in entities and isinstance(entities['datetime_str'], str):
            dt_str = entities['datetime_str']
            # This is a very basic placeholder.
            # A real implementation would use dateutil.parser.parse(dt_str).isoformat()
            # For now, we just ensure it's a string and pass it through.
            # Example: "tomorrow at 7pm" -> could be parsed to "YYYY-MM-DDTHH:MM:SS"
            print(f"Original datetime_str: '{dt_str}' (Skipping advanced parsing for now)")
            # entities['datetime_str_parsed'] = dt_str # Store as a new key or overwrite
        return entities

    def process_user_input(self, user_text: str) -> dict:
        """
        Processes user input text to extract intent and entities using Gemma.
        """
        # Ensure model is ready
        if not self.initialized:
            self.initialize_gemma()
            if not self.initialized:
                return {'intent': 'error', 'entities': {}, 'message': 'NLU service not available: initialization failed.'}

        # List of valid intents and entities for the prompt
        # (Extracted from the task description)
        valid_intents = [
            "book_table", "query_menu", "cancel_reservation", "greet", "goodbye",
            "affirm", "deny", "provide_information", "query_table_availability"
        ]
        # Example entities, not exhaustive, but to guide the model
        # Entities depend on intent.
        # book_table: num_guests, datetime_str, guest_name
        # cancel_reservation: reservation_id
        # query_menu: menu_item_query (e.g., "pizza", "drinks")
        # provide_information: (generic, depends on context)

        # Construct the few-shot prompt
        # The key is to make the LLM output JSON.
        # Using <|im_start|> and <|im_end|> tokens for chat-like structure if the model is fine-tuned for it.
        # For base models, simpler "User:" / "Assistant:" might be better. Gemma base models are not chat-tuned.
        # Let's use a simple User/Assistant structure.
        
        # For Gemma base models, a more direct instruction might be better.
        # The prompt structure is crucial.
        prompt = f"""You are a helpful restaurant booking assistant. Your task is to understand user requests, identify the intent, and extract relevant information (entities).
Respond with a JSON object containing "intent" and "entities".

Valid intents are: {', '.join(valid_intents)}.

Entities to extract for relevant intents:
- For "book_table": "num_guests" (integer), "datetime_str" (string like "today at 7pm" or "2024-08-15 19:00:00"), "guest_name" (string).
- For "cancel_reservation": "reservation_id" (integer or string).
- For "query_menu": "menu_item_query" (string, e.g., "pizza", "drinks", or general query).
- For "query_table_availability": "num_guests" (integer), "datetime_str" (string).
- For "provide_information": "info_topic" (string, what the user is providing info about), "info_value" (string, the actual info).
- For other intents like "greet", "goodbye", "affirm", "deny", "entities" should be an empty object.

Examples:
User: "Hello there"
Assistant: {{"intent": "greet", "entities": {{}}}}

User: "I want to book a table for 3 people for this Friday at 8 PM."
Assistant: {{"intent": "book_table", "entities": {{"num_guests": 3, "datetime_str": "this Friday at 8 PM"}}}}

User: "What's on your menu?"
Assistant: {{"intent": "query_menu", "entities": {{}}}}

User: "Show me tables for 2 for tomorrow evening"
Assistant: {{"intent": "query_table_availability", "entities": {{"num_guests": 2, "datetime_str": "tomorrow evening"}}}}

User: "My reservation ID is 12345"
Assistant: {{"intent": "provide_information", "entities": {{"info_topic": "reservation_id", "info_value": "12345"}}}}

User: "{user_text}"
Assistant: """ # The model should complete starting from here with the JSON.

        raw_llm_output = self.generate_text(prompt, max_new_tokens=150) # Max tokens for the JSON output

        if raw_llm_output.startswith("Error:"): # Handle generation errors
            return {'intent': 'error', 'entities': {}, 'message': raw_llm_output}

        # Attempt to parse the JSON output
        parsed_json = None
        try:
            # Try to find JSON within the output, as models might add extra text or markdown
            # Common pattern: ```json\n{...}\n``` or just {...}
            match = re.search(r'\{.*\}', raw_llm_output, re.DOTALL)
            if match:
                json_str = match.group(0)
                parsed_json = json.loads(json_str)
            else: # If no clear JSON block is found, try to parse the whole thing
                parsed_json = json.loads(raw_llm_output)
                
        except json.JSONDecodeError:
            print(f"NLU: Failed to parse JSON from LLM output: '{raw_llm_output}'")
            return {'intent': 'error', 'entities': {}, 'message': 'NLU processing failed: Could not parse JSON.', 'raw_output': raw_llm_output}

        if not isinstance(parsed_json, dict) or "intent" not in parsed_json or "entities" not in parsed_json:
            print(f"NLU: JSON output has incorrect structure: '{parsed_json}'")
            return {'intent': 'error', 'entities': {}, 'message': 'NLU processing failed: Incorrect JSON structure.', 'raw_output': raw_llm_output}

        # Normalize datetime entities if present
        if 'entities' in parsed_json and isinstance(parsed_json['entities'], dict):
            parsed_json['entities'] = self._parse_datetime_entities(parsed_json['entities'])
        
        return parsed_json


# Example of how it might be used
if __name__ == '__main__':
    print("Testing GemmaService NLU capabilities...")
    # Use a smaller model for quicker testing if available and configured, e.g. by passing model_name
    # gemma_service = GemmaService(model_name="google/gemma-2b") # Default
    # Or if you have a very small one fine-tuned for this, specify it.
    gemma_service = GemmaService() # Uses default model_name

    # Explicitly initialize or let process_user_input handle it.
    # For testing, explicit initialization gives more control over seeing logs.
    if not gemma_service.initialized:
        gemma_service.initialize_gemma()

    if gemma_service.initialized:
        test_inputs = [
            "Hi there!",
            "I'd like to book a table for 4 people for tomorrow at 7 PM.",
            "What kind of soups do you have?",
            "Thanks, goodbye.",
            "Cancel my booking, ID 789",
            "Is there a table for 2 available tonight around 8?",
            "Yes, that sounds good.",
            "My name is John Doe and the time is 6pm." # Test provide_information
        ]

        for user_input in test_inputs:
            print(f"\n--- Processing User Input: '{user_input}' ---")
            nlu_result = gemma_service.process_user_input(user_input)
            print(f"NLU Result: {json.dumps(nlu_result, indent=2)}")
            if 'raw_output' in nlu_result: # If parsing failed, print raw for debugging
                print(f"Raw LLM output for failed parse: {nlu_result['raw_output']}")
    else:
        print("\nGemma service could not be initialized. NLU tests skipped.")

    print(f"\nTest completed. Using model: {gemma_service.model_name} on device: {gemma_service.device}")
