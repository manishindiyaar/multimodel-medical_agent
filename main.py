import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

message = Mail(
    from_email='info@bladexlab.com',
    to_emails='manishindiyaar@gmail.com',
    subject='Test Email',
    plain_text_content='This is a test email'
)

try:
    sg = SendGridAPIClient(api_key="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")
    response = sg.send(message)
    print(response.status_code)
    print(response.body)
    print(response.headers)
except Exception as e:
    print(str(e))

    