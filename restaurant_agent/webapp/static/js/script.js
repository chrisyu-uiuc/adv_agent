document.addEventListener('DOMContentLoaded', () => {
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const chatbox = document.getElementById('chatbox');

    function displayMessage(message, sender, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        if (isError) {
            messageDiv.classList.add('error-message');
            messageDiv.textContent = message; // Error messages are typically strings
        } else {
            messageDiv.classList.add(sender === 'user' ? 'user-message' : 'agent-message');
            messageDiv.textContent = message;
        }
        chatbox.appendChild(messageDiv);
        chatbox.scrollTop = chatbox.scrollHeight; // Scroll to the bottom
    }

    async function sendMessageToServer(message) {
        try {
            const response = await fetch('/chat', { // Assuming API is on the same origin
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message }),
            });

            if (!response.ok) {
                // Try to parse error response from server if available
                let errorMsg = `Error: ${response.status} ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.detail || errorData.error_message || errorMsg;
                } catch (e) {
                    // Keep original errorMsg if response is not JSON or parsing fails
                }
                displayMessage(`Server error: ${errorMsg}`, 'agent', true);
                return;
            }

            const data = await response.json();
            if (data.response) {
                displayMessage(data.response, 'agent');
            } else if (data.error_message) {
                displayMessage(data.error_message, 'agent', true);
            }

        } catch (error) {
            console.error('Failed to send message or receive response:', error);
            displayMessage('Network error or server is unreachable. Please try again later.', 'agent', true);
        }
    }

    function handleSendMessage() {
        const message = userInput.value.trim();
        if (message) {
            displayMessage(message, 'user');
            sendMessageToServer(message);
            userInput.value = ''; // Clear input field
        }
    }

    sendButton.addEventListener('click', handleSendMessage);

    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            handleSendMessage();
        }
    });

    // Initial greeting or message from agent (optional)
    // displayMessage("Hello! I am your Restaurant Agent. How can I help you today?", 'agent');
});
