"""
Email Service for FailState
Handles sending verification and welcome emails
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
    """
    Send an email using SMTP
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email body
        text_content: Plain text fallback (optional)
    
    Returns:
        True if sent successfully, False otherwise
    """
    # Check if SMTP is configured
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured. Email not sent.")
        logger.info(f"Would send email to {to_email}: {subject}")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_USER
        msg['To'] = to_email
        
        # Add text version if provided
        if text_content:
            part1 = MIMEText(text_content, 'plain')
            msg.attach(part1)
        
        # Add HTML version
        part2 = MIMEText(html_content, 'html')
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


def send_verification_email(to_email: str, username: str, verification_link: str) -> bool:
    """
    Send email verification link to user
    
    Args:
        to_email: User's email address
        username: User's username
        verification_link: The verification URL
    
    Returns:
        True if sent successfully
    """
    subject = "Verify Your Email — FailState System"
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Verify Your Email</title>
  <style>
    body {{
      background: #07090d;
      color: #c9ccd6;
      font-family: 'Open Sans', Arial, sans-serif;
      margin: 0;
      padding: 0;
    }}
    .container {{
      max-width: 600px;
      margin: 0 auto;
      padding: 48px 24px;
    }}
    .logo {{
      font-size: 38px;
      font-weight: 700;
      letter-spacing: 1px;
      color: #e5e7eb;
      text-align: center;
      margin-bottom: 6px;
      text-shadow: 0 0 14px rgba(120, 160, 255, 0.25);
    }}
    .tagline {{
      text-align: center;
      font-size: 11px;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: #9ca3af;
      margin-bottom: 44px;
    }}
    .panel {{
      background: rgba(16, 18, 24, 0.72);
      border: 1px solid rgba(255,255,255,0.06);
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 0 80px rgba(0,0,0,0.8);
      backdrop-filter: blur(18px);
    }}
    h1 {{
      font-size: 22px;
      color: #e5e7eb;
      margin-bottom: 18px;
      font-weight: 600;
      letter-spacing: 0.5px;
    }}
    p {{
      font-size: 14px;
      line-height: 1.75;
      color: #b5b9c5;
      margin-bottom: 18px;
    }}
    .divider {{
      height: 1px;
      background: linear-gradient(to right, transparent, rgba(255,255,255,0.12), transparent);
      margin: 32px 0;
    }}
    .cta {{
      display: block;
      width: 100%;
      text-align: center;
      padding: 15px 0;
      margin-top: 28px;
      background: linear-gradient(135deg, rgba(90,130,255,0.25), rgba(120,170,255,0.15));
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
      color: #e5e7eb;
      text-decoration: none;
      letter-spacing: 2px;
      font-size: 12px;
      text-transform: uppercase;
      font-weight: 600;
    }}
    .footer {{
      margin-top: 44px;
      font-size: 11px;
      color: #6b7280;
      text-align: center;
      line-height: 1.6;
    }}
    .code {{
      font-family: 'Courier New', monospace;
      background: rgba(255,255,255,0.05);
      padding: 12px 16px;
      border-radius: 8px;
      color: #78a0ff;
      font-size: 16px;
      letter-spacing: 2px;
      text-align: center;
      margin: 20px 0;
      border: 1px solid rgba(255,255,255,0.08);
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">FailState</div>
    <div class="tagline">VERIFICATION REQUIRED</div>

    <div class="panel">
      <h1>Verify Your Email Address</h1>

      <p>
        Hello {username},
      </p>

      <p>
        Before you can access the system, you must verify your email address.
      </p>

      <p>
        This ensures that records are tied to verified accounts.
        This prevents noise.
        This maintains integrity.
      </p>

      <div class="divider"></div>

      <p>
        Click the button below to verify your email and activate your account:
      </p>

      <a href="{verification_link}" class="cta">VERIFY EMAIL</a>

      <div class="divider"></div>

      <p style="font-size: 12px; color: #6b7280;">
        If the button doesn't work, copy and paste this link into your browser:
      </p>
      <p style="font-size: 11px; color: #78a0ff; word-break: break-all;">
        {verification_link}
      </p>

      <div class="divider"></div>

      <p style="font-size: 12px; color: #9ca3af;">
        This link will expire in 24 hours.
      </p>
    </div>

    <div class="footer">
      This message was generated by the FailState System.<br/>
      You are receiving this because you requested to create an account.<br/>
      If you did not create this account, you may safely ignore this email.
    </div>
  </div>
</body>
</html>
    """
    
    text_content = f"""
FailState System - Email Verification

Hello {username},

Before you can access the system, you must verify your email address.

Verification Link:
{verification_link}

This link will expire in 24 hours.

If you did not create this account, you may safely ignore this email.

---
FailState System
    """
    
    return send_email(to_email, subject, html_content, text_content)


def send_welcome_email(to_email: str, username: str, login_link: str) -> bool:
    """
    Send welcome email after email verification
    
    Args:
        to_email: User's email address
        username: User's username
        login_link: Link to login/dashboard
    
    Returns:
        True if sent successfully
    """
    subject = "Access Granted — The System Has Logged You"
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Access Granted</title>
  <style>
    body {{
      background: #07090d;
      color: #c9ccd6;
      font-family: 'Open Sans', Arial, sans-serif;
      margin: 0;
      padding: 0;
    }}
    .container {{
      max-width: 600px;
      margin: 0 auto;
      padding: 48px 24px;
    }}
    .logo {{
      font-size: 38px;
      font-weight: 700;
      letter-spacing: 1px;
      color: #e5e7eb;
      text-align: center;
      margin-bottom: 6px;
      text-shadow: 0 0 14px rgba(120, 160, 255, 0.25);
    }}
    .tagline {{
      text-align: center;
      font-size: 11px;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: #9ca3af;
      margin-bottom: 44px;
    }}
    .panel {{
      background: rgba(16, 18, 24, 0.72);
      border: 1px solid rgba(255,255,255,0.06);
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 0 80px rgba(0,0,0,0.8);
      backdrop-filter: blur(18px);
    }}
    h1 {{
      font-size: 22px;
      color: #e5e7eb;
      margin-bottom: 18px;
      font-weight: 600;
      letter-spacing: 0.5px;
    }}
    p {{
      font-size: 14px;
      line-height: 1.75;
      color: #b5b9c5;
      margin-bottom: 18px;
    }}
    .divider {{
      height: 1px;
      background: linear-gradient(to right, transparent, rgba(255,255,255,0.12), transparent);
      margin: 32px 0;
    }}
    .cta {{
      display: block;
      width: 100%;
      text-align: center;
      padding: 15px 0;
      margin-top: 28px;
      background: linear-gradient(135deg, rgba(90,130,255,0.25), rgba(120,170,255,0.15));
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
      color: #e5e7eb;
      text-decoration: none;
      letter-spacing: 2px;
      font-size: 12px;
      text-transform: uppercase;
      font-weight: 600;
    }}
    .footer {{
      margin-top: 44px;
      font-size: 11px;
      color: #6b7280;
      text-align: center;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">FailState</div>
    <div class="tagline">STILL BROKEN. STILL HERE.</div>

    <div class="panel">
      <h1>Access Granted</h1>

      <p>
        You have entered the system.
      </p>

      <p>
        This platform exists because too many things remain broken — long after they were noticed, long after they were reported, long after they were meant to be fixed.
      </p>

      <p>
        Most of these failures fade.
        They are forgotten.
        They are buried under newer problems.
      </p>

      <p>
        Not here.
      </p>

      <div class="divider"></div>

      <p>
        When you log an issue, it becomes a record.
        It is timestamped.
        It is mapped.
        It is archived.
      </p>

      <p>
        And it is not kept silent.
      </p>

      <p>
        The system automatically notifies the authorities responsible for the region.
        If nothing changes, the system reminds them.
        If nothing changes again, the record remains.
      </p>

      <p>
        This does not guarantee resolution.
        It guarantees that unresolved things become difficult to erase.
      </p>

      <div class="divider"></div>

      <p>
        We do not argue.
        We do not persuade.
        We do not forget.
      </p>

      <p>
        We observe.
        We record.
        We persist.
      </p>

      <p>
        What you submit will remain visible.
        What remains unfixed will remain visible.
      </p>

      <div class="divider"></div>

      <p>
        This is not a helpdesk.
        This is not a promise.
        This is not a complaint box.
      </p>

      <p>
        This is a memory system for things that were easier to ignore.
      </p>

      <a href="{login_link}" class="cta">ENTER SYSTEM</a>
    </div>

    <div class="footer">
      This message was generated by the FailState System.<br/>
      You are receiving this because you created an account.<br/>
      Records do not decay.
    </div>
  </div>
</body>
</html>
    """
    
    text_content = f"""
FailState System - Access Granted

You have entered the system.

This platform exists because too many things remain broken — long after they were noticed, long after they were reported, long after they were meant to be fixed.

When you log an issue, it becomes a record. It is timestamped. It is mapped. It is archived. And it is not kept silent.

We do not argue. We do not persuade. We do not forget.
We observe. We record. We persist.

Enter System: {login_link}

---
This message was generated by the FailState System.
Records do not decay.
    """
    
    return send_email(to_email, subject, html_content, text_content)

