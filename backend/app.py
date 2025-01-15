import asyncio
import logging
from typing import Annotated
import re
import os
import requests
from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli, tokenize, tts
# from livekit.plugins.openai import openai
from livekit.agents.pipeline import VoicePipelineAgent, MultimodalAgent

from livekit.agents.llm import (
    ChatContext,
    ChatMessage,
    ChatImage
)
from livekit.plugins import deepgram, silero, cartesia, openai
from livekit.agents.voice_assistant import VoiceAssistant
from dotenv import load_dotenv


# load_dotenv(dotenv_path=".env.local")

load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("voice-agent")




class DentalAssistantFunction(agents.llm.FunctionContext):
    @agents.llm.ai_callable(
        description=(
            "called when asked to evalute dental issues using vission capabilities,"
            "for example, an image of teeth, gums, or the webcam feed showing the same. "
        )
    )
    async def analyze_dental_image(
        self,
        user_msg: Annotated[
            str,
            agents.llm.TypeInfo(
                description="The user message that triggered this function"
            )
        ],
    ):
        print(f"Analysing dental image : {user_msg}")
        return None
    
    @agents.llm.ai_callable(
        description="Assess the urgency of a dental issue based on the user's description."
    )
    async def assess_dental_urgency(
        self,
        sympotoms: Annotated[
            str,
            agents.llm.TypeInfo(
                description="The user's description of the dental issue"
            )
        ]
    ):
        urgent_keywords = ["sever pain", "swelling", "bleeding","trauma","knocked_out"]
        if any(keyword in sympotoms.lower() for keyword in urgent_keywords):
            return "urgent"
        else:
            return "not urgent"
        
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

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    print(f"Connected to room: {ctx.room.name}")

    chat_context = ChatContext(
        messages=[
            ChatMessage(
                role="system",
                content=(
                    "Your name is Daela, a dental assistant for Knolabs Dental Agency. You are soft, caring with a bit of humour in you when responding. "
                    "You offer appointment booking for dental care services, including urgent attention, routine check-ups, and long-term treatments available at prices according to needs which you cant say immediately. An onsite appointment is required."
                    "You can also analyze dental images to provide preliminary assessments, but always emphasize the need for professional in-person examination. "
                    "Provide friendly, professional assistance and emphasize the importance of regular dental care."
                    "The users asking you questions could be of different age. so ask questions one by one"
                    "Any query outside of the dental service, politely reject stating your purpose"
                    "When starting conversation try and get the patient's name and email address in sequence if not already provided. Encourage user to type email address to avoid any mistakes and reconfirm it after user provides it."
                    "If the care needed is not urgent, you can ask for image or ask user to show the dental area to use your vision capabilities to analyse the issue and offer assistance."
                    "always keep your conversation engaging, short and try to offer the in-person appointment."
                ),
            )
        ]
    )


    celebras=openai.with_cerebras(
            base_url="https://api.cerebras.ai/v1",
            api_key=os.environ.get("CEREBRAS_API_KEY"),
            model="llama3.1-8b",
        )
    dg=deepgram.STT()


    latest_image:rtc.VideoFrame | None = None

#     assistant = VoiceAssistant(
#     vad = silero.VAD.load(),
#     stt=dg,
#     llm=celebras,
#     tts=cartesia.TTS(voice="248be419-c632-4f23-adf1-5324ed7dbf1d"),
#     fnc_ctx=DentalAssistantFunction(),
#     chat_ctx=chat_context,
   

# )
    assistant = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=dg,
        llm=celebras,
        tts=cartesia.TTS(voice="248be419-c632-4f23-adf1-5324ed7dbf1d"),
        fnc_ctx=DentalAssistantFunction(),
        chat_ctx=chat_context,
    )

    agent = MultimodalAgent(
        vad=ctx.proc.userdata["vad"],
        stt=dg,
        llm=celebras,
        tts=cartesia.TTS(voice="248be419-c632-4f23-adf1-5324ed7dbf1d"),
        fnc_ctx=DentalAssistantFunction(),
        chat_ctx=chat_context,

    )

    chat = rtc.ChatManager(ctx.room)



    async def _answer(text:str, use_image:bool = False):
        content:list[str|ChatImage]=[text]
        if use_image and latest_image:
            print(f"Calling with Latest Image")
            content.append(ChatImage(image=latest_image))

        chat_context.messages.append(ChatMessage(
            role="user", content=content
        )) 
        stream =celebras.chat(chat_ctx=chat_context)
        await assistant.say(stream, allow_interruptions=True) 

    @chat.on("message_received")
    def on_message_received(msg: rtc.ChatMessage):
        if msg.message:
            asyncio.create_task(_answer(msg.message))
    @assistant.on("Function calls finished")
    def on_function_calls_finished(called_function:list[agents.llm.CalledFunction]):
        if len(called_function)==0:
            return
        function_name=called_function[0].call_info.function_info.name
        function_info.name
        print(function_name)
        if function_name == "assess_dental_urgency":
            urgency_result = function.result
            asyncio.create_task(_answer(urgency_result, use_image=False))
        elif function_name == "analyze_dental_image":
            user_instruction = called_function[0].call_info.function_info.arguments.get("user_msg")
            asyncio.create_task(_answer(user_instruction, use_image=True))

    assistant.start(ctx.room) 

    await asyncio.sleep(1)
    await assistant.say("Hello! I'm Daela, your dental assistant at Derma Co Dental Agency. Can I know if you are the patient or you're representing the patient?", allow_interruptions=True)

    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        video_track = await get_video_track(ctx.room)

        async for event in rtc.VideoStream(video_track):
            latest_image = event.frame
            asyncio.sleep(1)

    
    if __name__ == "__main__":
     cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))                    
