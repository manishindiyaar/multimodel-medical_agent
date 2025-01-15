import os
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import json

# Load environment variables
load_dotenv()

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-08-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def send_email(to_email: str, body_content: str, subject: str) -> dict:
    """Send an email using SendGrid."""
    sg = SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
    from_email = Email(
        email=os.getenv('MAIL_DEFAULT_SENDER'),
        name=os.getenv('MAIL_DEFAULT_SENDER_NAME', 'Appointment System')
    )

    content = f"""
    <!DOCTYPE html>
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            {body_content}
        </div>
    </body>
    </html>
    """

    message = Mail(
        from_email=from_email,
        to_emails=To(to_email),
        subject=subject,
        html_content=Content("text/html", content.strip())
    )

    try:
        sg.send(message)
        return {'status': 'success', 'message': f'Email sent successfully to {to_email}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

# Define the function schema for OpenAI
functions = [
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a specified address with the given content and subject",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_email": {
                        "type": "string",
                        "description": "The email address to send to"
                    },
                    "body_content": {
                        "type": "string",
                        "description": "The content/body of the email"
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject line of the email, should be concise and relevant to the content"
                    }
                },
                "required": ["to_email", "body_content", "subject"]
            }
        }
    }
]

def process_chat_message(user_message: str) -> str:
    """Process a chat message and execute appropriate actions."""
    
    # Create chat completion
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": """You are an AI assistant that helps with sending emails and managing appointments. 
                When a user wants to send an email:
                1. Extract the email address and content
                2. Generate a professional and relevant subject line based on the email content
                3. Format the email content professionally
                4. Use the send_email function with all components

                For subject lines:
                - Keep them concise (4-8 words)
                - Make them specific to the content
                - Use action words when appropriate
                - Maintain professional tone
                """
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        tools=functions
    )

    try:
        message = response.choices[0].message
        
        # Check if there's a function call
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            if tool_call.function.name == "send_email":
                # Parse the function arguments
                function_args = json.loads(tool_call.function.arguments)
                
                # Execute the send_email function
                result = send_email(
                    to_email=function_args["to_email"],
                    body_content=function_args["body_content"],
                    subject=function_args["subject"]
                )
                return f"Action completed: {result.get('message', str(result))}\nSubject used: {function_args['subject']}"
        
        # If no function call, return the message content
        return message.content
    
    except Exception as e:
        return f"An error occurred: {str(e)}"

def main():
    """Main chat loop."""
    print("Welcome to the AI Email Assistant! (Type 'quit' to exit)")
    print("Examples:")
    print("- send email to example@email.com with body Hello, I would like to schedule a meeting with you tomorrow.")
    print("- send email to user@company.com with body Please find attached the quarterly report highlights.")
    
    while True:
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() == 'quit':
            print("Goodbye!")
            break
            
        response = process_chat_message(user_input)
        print(f"\nAssistant: {response}")

if __name__ == "__main__":
    main()