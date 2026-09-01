import email.utils
from email.mime.multipart import MIMEMultipart
mime = MIMEMultipart("alternative")
mime["Subject"] = "Test"
mime["From"] = "me@example.com"
mime["To"] = "you@example.com"
mime["Date"] = email.utils.formatdate(localtime=True)
mime["Message-ID"] = email.utils.make_msgid(domain="voicecon.ai")
print(mime.as_string())
