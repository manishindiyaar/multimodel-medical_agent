# Program for saving the conversation history in json format for each chat messages
import logging
import random
import os
from typing import Annotated
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from dotenv import load_dotenv

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.pipeline import AgentCallContext, VoicePipelineAgent
from livekit.plugins import deepgram, openai, silero

# Load environment variables
load_dotenv('.env.local')

logger = logging.getLogger("email-assistant")
logger.setLevel(logging.INFO)

class ConversationLogger:
    def __init__(self):
        self.conversation = []
        self.start_time = datetime.now()

    def add_message(self, role: str, content: str):
        """Add a message to the conversation log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conversation.append({
            "timestamp": timestamp,
            "role": role,
            "content": content
        })

    def save_to_file(self):
        """Save the conversation to convo.txt."""
        try:
            with open("convo.txt", "a", encoding="utf-8") as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Conversation Start: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Conversation End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*50}\n\n")
                
                for msg in self.conversation:
                    f.write(f"[{msg['timestamp']}] {msg['role'].upper()}: {msg['content']}\n")
                
                f.write(f"\n{'='*50}\n\n")
            logger.info("Conversation saved to convo.txt")
        except Exception as e:
            logger.error(f"Failed to save conversation: {str(e)}")

class EmailAssistantFnc(llm.FunctionContext):
    """
    The class defines email-related LLM functions that the assistant can execute.
    """

    @llm.ai_callable()
    async def send_email(
        self,
        to_email: Annotated[
            str, llm.TypeInfo(description="The email address to send to")
        ],
        subject: Annotated[
            str, llm.TypeInfo(description="The subject line of the email")
        ],
        body_content: Annotated[
            str, llm.TypeInfo(description="The content/body of the email")
        ]
    ) -> str:
        """Called when the user wants to send an email. This function will send an email using SendGrid."""
        agent = AgentCallContext.get_current().agent
        conversation_logger = agent.conversation_logger  # Access the logger

        # Filler messages while processing
        if not agent.chat_ctx.messages or agent.chat_ctx.messages[-1].role != "assistant":
            filler_messages = [
                "I'll help you send that email right away.",
                "Let me send that email for you.",
                "Sending your email now."
            ]
            message = random.choice(filler_messages)
            logger.info(f"saying filler message: {message}")
            conversation_logger.add_message("assistant", message)  # Log the filler message
            speech_handle = await agent.say(message, add_to_chat_ctx=True)

        logger.info(f"sending email to {to_email}")
        
        try:
            # Initialize SendGrid
            sg = SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
            from_email = Email(
                email=os.getenv('MAIL_DEFAULT_SENDER'),
                name=os.getenv('MAIL_DEFAULT_SENDER_NAME', 'AI Assistant')
            )

            # Format email content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    {body_content}
                </div>
            </body>
            </html>
            """

            # Create and send email
            message = Mail(
                from_email=from_email,
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content.strip())
            )
            
            sg.send(message)
            result = f"Email sent successfully to {to_email}"
            logger.info(result)
            
            # Log the email details
            conversation_logger.add_message("system", f"Email sent: To: {to_email}, Subject: {subject}")
            
            return result

        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            conversation_logger.add_message("system", f"Error: {error_msg}")
            raise Exception(error_msg)


def prewarm_process(proc: JobProcess):
    # preload silero VAD in memory
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    fnc_ctx = EmailAssistantFnc()  # create our function context instance
    
    initial_chat_ctx = llm.ChatContext().append(
        text=(
            "You are an email assistant created by LiveKit. Your interface with users will be voice. "
            "You will help users send emails by collecting the recipient's email address, subject, and content. "
            "When sending emails:"
            "1. Ask for any missing information (email, subject, or content) if not provided"
            "2. Confirm the details before sending"
            "3. Format the content professionally"
            "4. Let users know when the email is being sent"
        ),
        role="system",
    )
    
    participant = await ctx.wait_for_participant()

    azuregpt = openai.LLM.with_azure(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
        api_version="2024-08-01-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        model="gpt-4"
    )
    
    # Create a conversation logger instance
    conversation_logger = ConversationLogger()
    
    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(),
        llm=azuregpt,
        tts=deepgram.TTS(
            model="aura-stella-en",
        ),
        fnc_ctx=fnc_ctx,
        chat_ctx=initial_chat_ctx,
    )
    
    # Add the conversation logger to the agent
    agent.conversation_logger = conversation_logger

    # Override the original say method to log messages
    original_say = agent.say
    async def say_with_logging(*args, **kwargs):
        if args:
            conversation_logger.add_message("assistant", args[0])
        return await original_say(*args, **kwargs)
    agent.say = say_with_logging

    # Override the original on_transcript method to log user messages
    original_on_transcript = agent._on_transcript
    def on_transcript_with_logging(*args, **kwargs):
        if args and len(args) > 1:
            conversation_logger.add_message("user", args[1])
        return original_on_transcript(*args, **kwargs)
    agent._on_transcript = on_transcript_with_logging

    # Start the assistant
    agent.start(ctx.room, participant)
    welcome_message = "Hello! I'm your email assistant. I can help you send emails - just let me know the recipient's address and what you'd like to say."
    await agent.say(welcome_message)

    try:
        # Wait for the session to complete
        await ctx.wait_for_disconnect()
    finally:
        # Save the conversation when the session ends
        conversation_logger.save_to_file()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm_process,
        ),
    )