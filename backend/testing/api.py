import enum
from typing import Annotated
from livekit.agents import llm
import logging
import os

logger = logging.getLogger("temperature-control")
logger.setLevel(logging.INFO)


class Zone(enum.Enum):
    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    OFFICE = "office"


class AssistantFnc(llm.FunctionContext):

    # def __init__(self) -> None:
    #     super().__init__()

    #     self._temperature = {
    #         Zone.LIVING_ROOM: 22,
    #         Zone.BEDROOM: 20,
    #         Zone.KITCHEN: 24,
    #         Zone.BATHROOM: 23,
    #         Zone.OFFICE: 21,
    #     }

    # @llm.ai_callable(description="get the temperature in a specific room")
    # def get_temperature(
    #     self, zone: Annotated[Zone, llm.TypeInfo(description="The specific zone")]
    # ):
    #     logger.info("get temp - zone %s", zone)
    #     temp = self._temperature[Zone(zone)]
    #     return f"The temperature in the {zone} is {temp}C"

    # @llm.ai_callable(description="set the temperature in a specific room")
    # def set_temperature(
    #     self,
    #     zone: Annotated[Zone, llm.TypeInfo(description="The specific zone")],
    #     temp: Annotated[int, llm.TypeInfo(description="The temperature to set")],
    # ):
    #     logger.info("set temo - zone %s, temp: %s", zone, temp)
    #     self._temperature[Zone(zone)] = temp
    #     return f"The temperature in the {zone} is now {temp}C"

    @llm.ai_callable(description="send an email to a specified address with the given content and subject")
    def send_email(
        self,
        to_email: Annotated[str, llm.TypeInfo(description="The email address to send to")],
        body_content: Annotated[str, llm.TypeInfo(description="The content/body of the email")],
        subject: Annotated[str, llm.TypeInfo(description="The subject line of the email")]
    ):
        """Send an email using SendGrid."""
        from dotenv import load_dotenv
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content

        # Load environment variables
        logger.info("Loading environment variables...")
        load_dotenv()

        api_key = os.getenv('SENDGRID_API_KEY')
        if not api_key:
            logger.error("SendGrid API key is missing in the environment variables.")
            return {'status': 'error', 'message': 'SendGrid API key is missing'}

        from_email_address = os.getenv('MAIL_DEFAULT_SENDER')
        if not from_email_address:
            logger.error("Default sender email address is missing in the environment variables.")
            return {'status': 'error', 'message': 'Default sender email address is missing'}

        from_email_name = os.getenv('MAIL_DEFAULT_SENDER_NAME', 'Appointment System')

        logger.info(f"Preparing to send email to {to_email} with subject '{subject}'")

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
            from_email=Email(email=from_email_address, name=from_email_name),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", content.strip())
        )

        try:
            logger.info("Sending email...")
            sg = SendGridAPIClient(api_key=api_key)
            response = sg.send(message)
            logger.info(f"Email sent successfully with status code: {response.status_code}")
            return {'status': 'success', 'message': f'Email sent successfully to {to_email}'}
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return {'status': 'error', 'message': str(e)}
