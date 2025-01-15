import logging
import asyncio
import os
import random
from typing import Annotated
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli, tokenize, tts

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.pipeline import VoicePipelineAgent, AgentCallContext
from livekit.plugins import openai, deepgram, silero, cartesia
from livekit.agents.llm import (
    ChatContext,
    ChatMessage,
    ChatImage
)
from api import AssistantFnc

load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("voice-agent")



# class DentalAssistantFunction(agents.llm.FunctionContext):

#     @agents.llm.ai_callable(
#         description=(
#             "called when asked to evalute dental issues using vission capabilities,"
#             "for example, an image of teeth, gums, or the webcam feed showing the same. "
#         )
#     )
#     async def analyze_dental_image(
#         self,
#         user_msg: Annotated[
#             str,
#             agents.llm.TypeInfo(
#                 description="The user message that triggered this function"
#             )
#         ],
#     ):
#         print(f"Analysing dental image : {user_msg}")
#         return None
    
#     @agents.llm.ai_callable(
#         description="Assess the urgency of a dental issue based on the user's description."
#     )
#     async def assess_dental_urgency(
#         self,
#         sympotoms: Annotated[
#             str,
#             agents.llm.TypeInfo(
#                 description="The user's description of the dental issue"
#             )
#         ]
#     ):
#         urgent_keywords = ["sever pain", "swelling", "bleeding","trauma","knocked_out"]
#         if any(keyword in sympotoms.lower() for keyword in urgent_keywords):
#             return "urgent"
#         else:
#             return "not urgent"



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


        
async def get_video_track(room: rtc.Room):
    video_track = asyncio.Future[rtc.RemoteVideoTrack]()
    for _, participate in room.remote_participants.items():
        for _, track_publication in participate.track_publications.items():
            if track_publication.track is not None and isinstance(track_publication.track, rtc.RemoteVideoTrack):
                video_track.set_result(track_publication.track)
                print(f"Using video track {track_publication.sid}")
                break

    return await video_track



# async def entrypoint(ctx: JobContext):
#     await ctx.connects()
#     print(f"Connected to room : {ctx.room.name}" )

#     chat_context = ChatContext(
#         messages=[
#             ChatMessage(
#                 role = "system",
#                 content=(
#                     "Your name is Daela , a dental assistant for Derma co Dental clinic"
#                 ),
#             )
#         ]
#     )



def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    # fnc_ctx = EmailAssistantFnc()
    fnc_ctx = AssistantFnc()
    chat_context = llm.ChatContext().append(
        role="system",
        text=(
                    # "Your name is Daela, a ai dental assistant at UAI wellbeong Clinic. You are soft, caring with a bit of humour in you when responding. "
                    # "You offer appointment booking for dental care services, including urgent attention, routine check-ups, and long-term treatments available at prices according to needs which you cant say immediately. An onsite appointment is required."
                    # "You can also analyze dental images to provide preliminary assessments, but always emphasize the need for professional in-person examination. "
                    # "Provide friendly, professional assistance and emphasize the importance of regular dental care."
                    # "The users asking you questions could be of different age. so ask questions one by one"
                    # "Any query outside of the dental service, politely reject stating your purpose"
                    # "When starting conversation try and get the patient's name and email address in sequence if not already provided. Encourage user to type email address to avoid any mistakes and reconfirm it after user provides it."
                    # "If the care needed is not urgent, you can ask for image or ask user to show the dental area to use your vision capabilities to analyse the issue and offer assistance."
                    # "always keep your conversation engaging, short and try to offer the in-person appointment."
                #     """You are an AI assistant that helps with sending emails and managing appointments. 
                # When a user wants to send an email, extract the email address and content, then use the send_email function.
                # Format the email content professionally."""
            #      "You are a voice assistant created by LiveKit. Your interface with users will be voice. "
            # "You should use short and concise responses, and avoiding usage of unpronouncable punctuation."

            """You are an AI assistant that helps with sending emails and managing appointments. 
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
        ),
    )
    latest_image: rtc.VideoFrame | None = None

    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)

    # Wait for the first participant to connect
    participant = await ctx.wait_for_participant()
    logger.info(f"starting voice assistant for participant {participant.identity}")

    # This project is configured to use Deepgram STT, OpenAI LLM and TTS plugins
    # Other great providers exist like Cartesia and ElevenLabs
    # Learn more and pick the best one for your app:
    # https://docs.livekit.io/agents/plugins

    
    
    azuregpt = openai.LLM.with_azure(
        api_key = os.getenv("AZURE_OPENAI_API_KEY"),  
        api_version = "2024-08-01-preview",
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"),
        model = "gpt-4"
    )

    # azuregpt = openai.LLM.with_vertex(model="google/gemini-2.0-flash-exp")
    

    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(),

        # llm=openai.LLM.with_cerebras(
        #     base_url="https://api.cerebras.ai/v1",
        #     api_key=os.environ.get("CEREBRAS_API_KEY"),
        #     model="llama3.1-8b",
        # ),

        # llm=azuregpt,
        # # tts=openai.TTS(),
        # tts=cartesia.TTS(voice="248be419-c632-4f23-adf1-5324ed7dbf1d"),
        # llm=openai.LLM.with_vertex(model="google/gemini-2.0-flash-exp"),
        llm=azuregpt,
        tts=deepgram.TTS(
            model="aura-stella-en",
        ),
        # fnc_ctx=DentalAssistantFunction(),
        fnc_ctx=fnc_ctx,
        chat_ctx=chat_context,
    )

   

    # chat = rtc.ChatManager(ctx.room)

    agent.start(ctx.room, participant)

    chat = rtc.ChatManager(ctx.room)

    async def _answer(text: str, use_image: bool = False):
        content: list[str | ChatImage] = [text]
        if use_image and latest_image:
            print(f"Calling with latest image")
            content.append(ChatImage(image=latest_image))

        chat_context.messages.append(ChatMessage(role="user", content=content))
        stream = azuregpt.chat(chat_ctx=chat_context)
        await agent.say(stream, allow_interruptions=True)

    
    @chat.on("message_received")
    def on_message_received(msg: rtc.ChatMessage):
        if msg.message:
            asyncio.create_task(_answer(msg.message))

    @agent.on("function_calls_finished")
    def on_function_calls_finished(called_functions: list[agents.llm.CalledFunction]):
        if not called_functions:
            return
        
        function_name=called_functions[0].call_info.function_info.name
        print(function_name)
        if function_name == "assess_dental_urgency":
            urgency_result = function.result
            asyncio.create_task(_answer(urgency_result,  use_image=False))
        
        elif function_name == "analyze_dental_image":
            user_instruction = called_functions[0].call_info.arguments.get("user_msg")
            asyncio.create_task(_answer(user_instruction, use_image=True))


    agent.start(ctx.room)

    await asyncio.sleep(1)
    # await agent.say("Hello! I'm Mira, your dental assistant at UAI wellbeing clinic. Can I know if you are the patient or you're representing the patient?", allow_interruptions=True)

    await agent.say("Hello!", allow_interruptions=True)

    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        video_track = await get_video_track(ctx.room)

        async for event in rtc.VideoStream(video_track):
            latest_image = event.frame
            asyncio.sleep(1)


    # The agent should be polite and greet the user when it joins :)
    # await agent.say("Hey, how can I help you today?", allow_interruptions=True)

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
