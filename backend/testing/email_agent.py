import logging
import random
import os
from typing import Annotated
from livekit import agents, rtc
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

        # Filler messages while processing
        if not agent.chat_ctx.messages or agent.chat_ctx.messages[-1].role != "assistant":
            filler_messages = [
                "I'll help you send that email right away.",
                "Let me send that email for you.",
                "Sending your email now."
            ]
            message = random.choice(filler_messages)
            logger.info(f"saying filler message: {message}")
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
            return result

        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)


def prewarm_process(proc: JobProcess):
    # preload silero VAD in memory
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
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

    # Start the assistant
    agent.start(ctx.room, participant)
    
    chat = rtc.ChatManager(ctx.room)
    await agent.say(
        "Hello! I'm your email assistant. I can help you send emails - just let me know the recipient's address and what you'd like to say."
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm_process,
        ),
    )