# using SendGrid's Python Library
# https://github.com/sendgrid/sendgrid-python
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from ai import send_email


message = Mail(
    from_email='info@bladexlab.com',
    to_emails='manishindiyaar@gmail.com',
    subject='Sending with Twilio SendGrid is Fun',
    html_content='<strong>and easy to do anywhere, even with Python</strong>')
try:
    sg = SendGridAPIClient(api_key="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")
    # response = sg.send(message)
    response = send_email(message)
    

    print(response.status_code)
    print(response.body)
    print(response.headers)
except Exception as e:
    print(e.message)