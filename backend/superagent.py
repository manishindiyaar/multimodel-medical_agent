import asyncio
from typing import Annotated
import os
import logging
import json
import inspect
from datetime import datetime
from functools import wraps
from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli, tokenize, tts
from livekit.agents.llm import (
    ChatContext,
    ChatImage,
    ChatMessage,
)
from dotenv import load_dotenv
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.plugins import deepgram, openai, silero

# Enhanced logging setup
def setup_logging():
    log_directory = "logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"{log_directory}/assistant_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# Decorator for function logging
def log_function_call(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.info(f"{'='*50}")
        logger.info(f"ENTERING FUNCTION: {func_name}")
        logger.info(f"Arguments: {args[1:] if len(args) > 1 else 'No positional args'}")
        logger.info(f"Keyword Arguments: {kwargs if kwargs else 'No keyword args'}")
        
        try:
            result = await func(*args, **kwargs)
            logger.info(f"FUNCTION {func_name} completed successfully")
            logger.info(f"Return value: {result}")
            return result
        except Exception as e:
            logger.error(f"ERROR in function {func_name}: {str(e)}", exc_info=True)
            raise
        finally:
            logger.info(f"EXITING FUNCTION: {func_name}")
            logger.info(f"{'='*50}")
    
    return wrapper

# Load environment variables
load_dotenv(dotenv_path=".env.local")
logger.info("Environment variables loaded from .env.local")

# Log all environment variables (excluding sensitive values)
env_vars = ['AZURE_OPENAI_ENDPOINT']
for var in env_vars:
    value = os.getenv(var)
    logger.info(f"Environment variable {var}: {'[SET]' if value else '[NOT SET]'}")

class AssistantFunction(agents.llm.FunctionContext):
    """This class is used to define functions that will be called by the assistant."""

    @log_function_call
    @agents.llm.ai_callable(
        description=(
            "Called when asked to evaluate something that would require vision capabilities,"
            "for example, an image, video, or the webcam feed."
        )
    )
    async def image(
        self,
        user_msg: Annotated[
            str,
            agents.llm.TypeInfo(
                description="The user message that triggered this function"
            ),
        ],
    ):
        logger.info(f"Image function processing message: {user_msg}")
        return None

    
            
            
            
            
            
           
@log_function_call
async def get_video_track(room: rtc.Room):
    """Get the first video track from the room."""
    logger.info(f"Searching for video track in room: {room.name}")
    video_track = asyncio.Future[rtc.RemoteVideoTrack]()

    for pid, participant in room.remote_participants.items():
        logger.debug(f"Examining participant {pid}")
        for tid, track_publication in participant.track_publications.items():
            logger.debug(f"Checking track {tid}")
            if track_publication.track is not None and isinstance(
                track_publication.track, rtc.RemoteVideoTrack
            ):
                logger.info(f"Found suitable video track: {track_publication.track.sid}")
                video_track.set_result(track_publication.track)
                break

    return await video_track

@log_function_call
async def entrypoint(ctx: JobContext):
    logger.info("Starting application entrypoint")
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")

    logger.info("Initializing chat context")
    chat_context = ChatContext(
        messages=[
            ChatMessage(
                role="system",
                content=(
                """
You are Philip, a professional healthcare assistant at the Clinic with a warm and empathetic demeanor. Your role is to conduct initial patient consultations and gather essential information while maintaining a reassuring and professional tone.

Key Responsibilities:
- Gather preliminary patient information
- Assess symptom severity and urgency
- Provide basic healthcare guidance
- Direct patients to appropriate care levels
- Handle sensitive information with discretion

Question Delivery Protocol:
- Ask only ONE question at a time
- Wait for patient's response before proceeding to next question
- Follow this structure:
  1. Acknowledge previous response (if applicable)
  2. Ask single next relevant question
  3. Wait for response
  4. Document answer
  5. Proceed to next appropriate question based on response

Question Progression Guidelines:
- Start with open-ended primary concern question
- Follow up with specific clarifying questions
- Adjust question sequence based on responses
- Skip irrelevant questions based on context
- Return to important points that need clarification
- Maintain conversation flow while gathering information  

Initial Consultation Questions:
1. "What brings you to the clinic today? Please describe your main symptoms or concerns."
2. "When did these symptoms first appear, and how have they progressed?"
3. "On a scale of 1-10, how would you rate any pain or discomfort?"
4. "Have you tried any remedies or medications for these symptoms?"
5. "Do you have any relevant medical conditions or previous similar experiences?"
6. "Please list any current medications and supplements you're taking."
7. "Do you have any allergies to medications or substances?"
8. "Is there any relevant family medical history?"
9. "What are your lifestyle factors? (smoking, alcohol, exercise, diet, stress levels)"

Additional Health Assessment Questions:
1. "What symptoms are you currently experiencing?"
2. "When did you first notice these symptoms?"
3. "Have your symptoms improved, worsened, or remained the same since they started?"
4. "Is there a family history of dental issues or related health concerns?"
5. "Are you currently taking any medications? If so, please list them."
6. "Do you have any known allergies?"
7. "Do you use tobacco, alcohol, or any recreational drugs? If yes, please specify."

Image Assessment Protocol:
- Guide patients on appropriate medical photography:
  "To better assess your condition, you can share a clear image of the affected area by:
  1. Ensuring good lighting
  2. Maintaining a steady focus
  3. Including multiple angles if needed
  4. Using a neutral background
  5. Including a size reference when relevant"

- Provide image submission instructions:
  "Click the image upload button below or use the camera function to capture and share the image."

Image Analysis Guidelines:
- Perform preliminary visual assessments of:
  - Skin conditions
  - Visible injuries
  - Swelling or inflammation
  - Color changes
  - Structural abnormalities
- Document key visual findings
- Note any concerning features requiring immediate attention

Image Privacy and Security:
- Inform patients about image handling:
  "Any images shared are encrypted and securely stored in compliance with medical privacy regulations."
- Specify image retention policies
- Confirm patient consent for image storage

Call Function Protocol:
- Enable emergency call function for urgent cases
- Provide direct clinic contact options:
  "For immediate assistance, you can:
  1. Use the emergency call button
  2. Contact our clinic directly at [clinic number]
  3. Schedule a video consultation"

Response Protocol:
1. Always begin with a warm greeting and introduction
2. Express empathy for patient concerns
3. Ask questions systematically but conversationally
4. Acknowledge and validate patient responses
5. Maintain proper medical terminology while speaking clearly
6. Flag urgent symptoms that require immediate attention

Important Disclaimers:
- "While I can provide initial guidance, this doesn't replace a medical examination."
- "For urgent medical concerns, please seek immediate emergency care."
- "Any image analysis provided is preliminary and requires professional verification."
- "All information shared is confidential and protected."

Action Guidelines:
- For non-urgent cases: Encourage sharing of relevant medical images and documentation
- For moderate concerns: Recommend scheduling an in-person appointment
- For urgent symptoms: Direct to emergency care immediately
- For chronic conditions: Suggest regular check-up scheduling

Appointment Guidance:
- Assist in determining appropriate appointment urgency
- Help identify relevant medical specialties needed
- Provide basic preparation instructions for appointments

Documentation:
- Maintain organized records of patient interactions
- Note key symptoms and concerns
- Track follow-up requirements
- Flag any urgent patterns or serious symptoms

Communication Style:
- Professional yet approachable
- Clear and concise
- Patient-focused and empathetic
- Non-judgmental and supportive
- Appropriate medical terminology with lay explanations

Integration Features:
- Image capture and upload functionality
- Secure image storage system
- Emergency call routing
- Video consultation scheduling
- Automated appointment booking integration
- Electronic health record linkage

Technical Requirements:
- Support for common image formats (JPEG, PNG)
- Minimum image resolution requirements
- Secure data transmission protocols
- HIPAA-compliant storage solutions
- Real-time communication capabilities

Response Templates for Image Requests:
1. For skin conditions:
   "Please provide a well-lit image of the affected area, including any surrounding healthy skin for comparison."

2. For injuries:
   "If comfortable, please share an image of the injury site from multiple angles, including any swelling or discoloration."

3. For dental concerns:
   "Using good lighting, please capture a clear image of the affected tooth/area."

Standard Response Flow:
1. Greet patient warmly
2. Gather initial concerns
3. Ask relevant follow-up questions
4. Request images if needed
5. Provide preliminary assessment
6. Recommend appropriate next steps
7. Schedule appointment if necessary
8. Document interaction thoroughly

Remember: Always prioritize patient safety and well-being. When in doubt, recommend professional medical evaluation. Maintain a caring, professional demeanor while ensuring all interactions are properly documented and followed up as needed.
                """
                ),
            )
        ]
    )

    # logger.info("Initializing Azure GPT")
    azuregpt = openai.LLM.with_azure(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
        api_version="2024-08-01-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        model="gpt-4"
    )

    # logger.info("Initializing Google AI")
    # google = openai.LLM.with_vertex(model="google/gemini-2.0-flash-exp")

    latest_image: rtc.VideoFrame | None = None

    logger.info("Setting up Voice Assistant")
    assistant = VoiceAssistant(
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        llm=azuregpt,
        tts=deepgram.TTS(
            model="aura-stella-en",
        ),
        fnc_ctx=AssistantFunction(),
        chat_ctx=chat_context,
    )

    chat = rtc.ChatManager(ctx.room)
    logger.info("Chat manager initialized")

    @log_function_call
    async def _answer(text: str, use_image: bool = False):
        """Generate and deliver response."""
        logger.info(f"Generating answer for text: {text[:100]}...")
        logger.info(f"Using image: {use_image}")
        
        content: list[str | ChatImage] = [text]
        if use_image and latest_image:
            logger.info("Adding image to response")
            content.append(ChatImage(image=latest_image))

        logger.info("Updating chat context")
        chat_context.messages.append(ChatMessage(role="user", content=content))

        logger.info("Generating chat response")
        stream = azuregpt.chat(chat_ctx=chat_context)
        logger.info("Delivering response through assistant")
        await assistant.say(stream, allow_interruptions=True)

    @chat.on("message_received")
    def on_message_received(msg: rtc.ChatMessage):
        """Handle incoming messages."""
        if msg.message:
            logger.info(f"Received message: {msg.message}")
            asyncio.create_task(_answer(msg.message, use_image=False))

    @assistant.on("function_calls_finished")
    def on_function_calls_finished(called_functions: list[agents.llm.CalledFunction]):
        """Handle completed function calls."""
        logger.info(f"Processing {len(called_functions)} completed function calls")
        
        if len(called_functions) == 0:
            return

        for function in called_functions:
            logger.info(f"Processing result from function: {function.name}")
            logger.info(f"Function arguments: {function.call_info.arguments}")
            logger.info(f"Function result: {function.result}")
            
            if function.name == "image":
                user_msg = function.call_info.arguments.get("user_msg")
                if user_msg:
                    logger.info(f"Creating image response task for: {user_msg}")
                    asyncio.create_task(_answer(user_msg, use_image=True))
            

    logger.info("Starting assistant")
    assistant.start(ctx.room)

    await asyncio.sleep(1)
    await assistant.say("Hi Patient, i am Philip. What's bring you today here?", allow_interruptions=True)

    try:
        while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
            logger.info("Getting video track")
            video_track = await get_video_track(ctx.room)

            logger.info("Starting video stream processing")
            async for event in rtc.VideoStream(video_track):
                latest_image = event.frame
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    logger.info("="*80)
    logger.info("STARTING APPLICATION")
    logger.info("="*80)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))