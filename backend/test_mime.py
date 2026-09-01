from email.mime.multipart import MIMEMultipart
mime = MIMEMultipart("alternative")
mime["Subject"] = "Test"
mime["From"] = "me@example.com"
mime["To"] = "you@example.com"
print(mime.as_string())
