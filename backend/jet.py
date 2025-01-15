import logging
import random
import re
import os
import urllib.parse
from typing import Annotated

import aiohttp
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

# Configure logging
logger = logging.getLogger("weather-assistant")
logger.setLevel(logging.INFO)

class AssistantFunctions(llm.FunctionContext):
    """
    Defines LLM functions for the weather assistant.
    """

    @llm.ai_callable()
    async def get_weather(
        self, 
        location: Annotated[str, llm.TypeInfo(description="Location for weather information")]
    ):
        """Retrieve weather information for a specified location."""
        # Sanitize location input
        location = re.sub(r"[^a-zA-Z0-9\s]+", "", location).strip()

        # Get current agent context
        agent = AgentCallContext.get_current().agent

        # Provide filler messages
        if not agent.chat_ctx.messages or agent.chat_ctx.messages[-1].role != "assistant":
            filler_messages = [
                f"Checking the weather in {location} for you.",
                f"Let me fetch the current weather conditions in {location}.",
                f"Weather update for {location} coming right up."
            ]
            message = random.choice(filler_messages)
            logger.info(f"Filler message: {message}")
            await agent.say(message, add_to_chat_ctx=True)

        # Fetch weather data
        try:
            url = f"https://wttr.in/{urllib.parse.quote(location)}?format=%C+%t"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        weather_data = await response.text()
                        formatted_weather = f"The weather in {location} is {weather_data.strip()}."
                        logger.info(f"Weather data retrieved: {formatted_weather}")
                        return formatted_weather
                    else:
                        raise Exception(f"Weather API request failed: {response.status}")
        except Exception as e:
            logger.error(f"Weather retrieval error: {e}")
            return f"Sorry, I couldn't retrieve the weather for {location}."

def prewarm_process(proc: JobProcess):
    """Preload Silero VAD for faster session initialization."""
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    """Main entry point for the weather assistant."""
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    # Initialize function context
    fnc_ctx = AssistantFunctions()
    
    # Configure initial chat context
    initial_chat_ctx = llm.ChatContext().append(
        text=(
            "You are a voice-activated weather assistant. "
            "Provide concise, friendly weather information. "
            "Interact naturally and help users get weather details quickly."
        ),
        role="system",
    )

    # Wait for participant
    participant = await ctx.wait_for_participant()

    # Configure Azure OpenAI
    azuregpt = openai.LLM.with_azure(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
        api_version="2024-08-01-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        model="gpt-4"
    )

    # Create voice pipeline agent
    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(),
        llm=azuregpt,
        tts=deepgram.TTS(model="aura-stella-en"),
        fnc_ctx=fnc_ctx,
        chat_ctx=initial_chat_ctx,
    )

    # Start agent and welcome message
    agent.start(ctx.room, participant)
    await agent.say(
        "Hello! I'm your weather assistant. Which location's weather would you like to know?"
    )

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm_process,
        ),
    )
