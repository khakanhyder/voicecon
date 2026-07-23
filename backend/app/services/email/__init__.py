"""
Email service package.

Public entrypoint: ``email_service`` — a process-wide EmailService that picks a
provider (SMTP / SendGrid / console) from settings at first use. See service.py.
"""
from app.services.email.service import EmailService, email_service
from app.services.email.base import EmailMessage, EmailProvider

__all__ = ["EmailService", "email_service", "EmailMessage", "EmailProvider"]
