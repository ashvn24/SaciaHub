import sendgrid
import os
import re
import base64
from sendgrid.helpers.mail import *
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

from_mail = os.environ.get('EMAIL')

# Function to encode the logo in Base64
def get_encoded_logo():
    logo_path = os.path.join(os.path.dirname(__file__), 'logo', 'logo.webp')  # Path to the logo
    with open(logo_path, "rb") as image_file:
        image_data = image_file.read()
    encoded_logo = base64.b64encode(image_data).decode('utf-8')
    return encoded_logo

def encoded_linkedin():
    logo_path = os.path.join(os.path.dirname(__file__), 'logo', 'Linkedin.png')  # Path to the logo
    with open(logo_path, "rb") as image_file:
        image_data = image_file.read()
    encoded_logo = base64.b64encode(image_data).decode('utf-8')
    return encoded_logo

def encoded_twitter():
    logo_path = os.path.join(os.path.dirname(__file__), 'logo', 'twitter.png')  # Path to the logo
    with open(logo_path, "rb") as image_file:
        image_data = image_file.read()
    encoded_logo = base64.b64encode(image_data).decode('utf-8')
    return encoded_logo

def encoded_world():
    logo_path = os.path.join(os.path.dirname(__file__), 'logo', 'World.png')  # Path to the logo
    with open(logo_path, "rb") as image_file:
        image_data = image_file.read()
    encoded_logo = base64.b64encode(image_data).decode('utf-8')
    return encoded_logo



def send_mail_func(to, FirstName, password, subject, company_portal_url=None):
    if is_email(to):
        try:
            return send_mail(to, FirstName, password, subject, company_portal_url)
        except Exception as e:
            print(f"Error sending email: {e}")
            raise e
    elif is_phone_number(to):
        return send_sms(to, FirstName, password, subject, company_portal_url)
    else:
        raise ValueError("Invalid email or phone number")


def is_email(address):
    return re.match(r"[^@]+@[^@]+\.[^@]+", address)


def is_phone_number(number):
    return re.match(r"^\+?[1-9]\d{1,14}$", number)


def send_mail(email, FirstName, password, subject, company_portal_url=None, title=None, timesheet_status=None, admin_name=None, timesheet_date=None, subj_data=None, type=None):
    print("DATA",email, FirstName, password, subject, company_portal_url, title, timesheet_status, admin_name, timesheet_date, subj_data, type)
    # subj = "Welcome to BlackRock IT Solutions!"
    # if subject == "reset":
    #     subj = "Reset Your Password - Action Required"
    #     template_path = os.path.join(os.path.dirname(__file__), 'templates', 'reset.html')
    # elif subject == 'welcome':
    #     subj = "Welcome to BlackRock IT Solutions!"
    #     template_path = os.path.join(os.path.dirname(__file__), 'templates', 'welcome_email.html')
    # elif subject == '2fa':
    #     subj = "2FA Code"
    #     template_path = os.path.join(os.path.dirname(__file__), 'templates', 'TwoFa.html')
    # elif subject == 'Request Notification':
    #     subj = "Request Notification"
    #     title = "Request Status"
    #     template_path = os.path.join(os.path.dirname(__file__), 'templates', 'request.html')
    # elif subject == 'Timesheet Notification':
    #     subj = "Timesheet Notification"
    #     title = "Timesheet Status"
    #     template_path = os.path.join(os.path.dirname(__file__), 'templates', 'Notification.html')
    # elif subject in ['Timesheet Notification Admin', 'Request Notification Admin']:
    #     subj = "Timesheet" if subject == 'Timesheet Notification Admin' else "Request"
    #     title = "Timesheet Received" if subject == 'Timesheet Notification Admin' else "Request Received"
    #     template_path = os.path.join(os.path.dirname(__file__), 'templates', 'admin.html')

    # with open(template_path, 'r') as file:
    #     html_content = file.read()

    # if company_portal_url and not company_portal_url.startswith(('http://', 'https://')):
    #     company_portal_url = f"https://{company_portal_url}/set-password?email={email}&token={password}"

    # html_content = html_content.replace("{{name}}", FirstName or "")
    # html_content = html_content.replace("{{action_url}}", company_portal_url or "")
    # html_content = html_content.replace("{{username}}", email or "")
    # html_content = html_content.replace("{{Password}}", password or "")
    # html_content = html_content.replace("{{title}}", title or "")
    # html_content = html_content.replace("{{timesheet_status}}", timesheet_status or "")
    # html_content = html_content.replace("{{admin_name}}", admin_name or "")
    # html_content = html_content.replace("{{timesheet_date}}", timesheet_date or "")
    # html_content = html_content.replace("{{subj}}", subj_data or "")
    # html_content = html_content.replace("{{type}}", type or "")

    # # Replace base64 placeholders with CIDs
    # html_content = html_content.replace("{{logo}}", "cid:logo")
    # html_content = html_content.replace("{{linkedin}}", "cid:linkedin")
    # html_content = html_content.replace("{{twitter}}", "cid:twitter")
    # html_content = html_content.replace("{{world}}", "cid:world")
    # html_content = html_content.replace("{{step1}}", "cid:step1")
    # html_content = html_content.replace("{{step2}}", "cid:step2")
    

    # if password and subject in ["reset", "2fa"]:
    #     for i, digit in enumerate(list(password), start=1):
    #         html_content = html_content.replace(f"{{{{Password_{i}}}}}", digit)
    
    # sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))
    # print("API Key:", os.environ.get('SENDGRID_API_KEY'))
    # from_email = Email(from_mail)
    # to_email = To(email)
    # content = Content("text/html", html_content)
    # mail = Mail(from_email, to_email, subj, content)

    # # Attach images using CID
    # def attach_image(path, cid):
    #     with open(path, 'rb') as f:
    #         data = f.read()
    #     encoded = base64.b64encode(data).decode()
    #     attachment = Attachment()
    #     attachment.file_content = FileContent(encoded)
    #     attachment.file_type = FileType('image/png')  # or 'image/webp' based on actual file
    #     attachment.file_name = FileName(os.path.basename(path))
    #     attachment.disposition = Disposition('inline')
    #     attachment.content_id = ContentId(cid)
    #     mail.add_attachment(attachment)

    # base_dir = os.path.join(os.path.dirname(__file__), 'logo')
    # attach_image(os.path.join(base_dir, 'logo.webp'), 'logo')
    # attach_image(os.path.join(base_dir, 'Linkedin.png'), 'linkedin')
    # attach_image(os.path.join(base_dir, 'twitter.png'), 'twitter')
    # attach_image(os.path.join(base_dir, 'World.png'), 'world')
    # if subject == 'welcome':
    #     attach_image(os.path.join(base_dir, 'Step1.png'), 'step1')
    #     attach_image(os.path.join(base_dir, 'Step2.png'), 'step2')

    # response = sg.client.mail.send.post(request_body=mail.get())
    return response





def send_sms(phone_number, FirstName, password, subject, company_portal_url=None):
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_phone_number = os.environ.get('TWILIO_PHONE_NUMBER')

    client = Client(account_sid, auth_token)

    message_body = f"Hello {FirstName}, "
    if subject == "reset":
        message_body += f"Verify using this otp: {password}"
    elif subject == 'welcome':
        message_body += "welcome to BlackRock IT Solutions! Set your password using this link: "
    elif subject == '2fa':
        message_body += "your 2FA code is: "

    if company_portal_url:
        if not company_portal_url.startswith('http://') and not company_portal_url.startswith('https://'):
            company_portal_url = f"https://{company_portal_url}/set-password/{phone_number}/{password}"
        message_body += company_portal_url

    response = client.messages.create(
        body=message_body,
        from_=twilio_phone_number,
        to=phone_number
    )
    return response