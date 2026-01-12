"""
Email Service for FailState
Handles sending verification and welcome emails
Supports both Resend API (recommended) and SMTP
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Try to import resend (optional)
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend not installed. Will use SMTP only.")


def send_email_resend(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
    """
    Send email using Resend API (recommended for cloud platforms)
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email body
        text_content: Plain text fallback (optional)
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not RESEND_AVAILABLE:
        logger.warning("Resend package not available - install with: pip install resend")
        return False
    
    # Check if Resend API key is configured
    resend_api_key = getattr(settings, 'RESEND_API_KEY', None)
    if not resend_api_key:
        logger.warning("RESEND_API_KEY environment variable not set")
        return False
    
    logger.info(f"Attempting to send email via Resend to {to_email}")
    
    try:
        resend.api_key = resend_api_key
        
        # Get from email (use configured or default)
        from_email = getattr(settings, 'SMTP_USER', 'onboarding@resend.dev')
        
        # If no custom email configured, use Resend's test domain
        if not from_email or from_email == 'noreply@failstate.in':
            from_email = 'onboarding@resend.dev'
            logger.info("Using Resend test domain (onboarding@resend.dev)")
        
        # Add proper headers to avoid spam
        params = {
            "from": f"FailState System <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
            "headers": {
                "X-Entity-Ref-ID": "failstate-system",
                "List-Unsubscribe": f"<mailto:{from_email}?subject=unsubscribe>",
            }
        }
        
        if text_content:
            params["text"] = text_content
        
        logger.info(f"Sending email from {from_email} to {to_email}")
        email = resend.Emails.send(params)
        logger.info(f"✅ Email sent successfully via Resend to {to_email}. ID: {email.get('id', 'unknown')}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send email via Resend to {to_email}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        return False


def send_email_smtp(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
    """
    Send email using SMTP (fallback method)
    
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
        logger.debug("SMTP not configured")
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
        
        # Send email with timeout to prevent hanging
        # Use SSL (port 465) or TLS (port 587) based on SMTP_PORT
        smtp_port = int(settings.SMTP_PORT)
        
        if smtp_port == 465:
            # Use SMTP_SSL for port 465 (GoDaddy/Secureserver)
            with smtplib.SMTP_SSL(settings.SMTP_HOST, smtp_port, timeout=10) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            # Use SMTP with STARTTLS for port 587 (standard)
            with smtplib.SMTP(settings.SMTP_HOST, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
        
        logger.info(f"Email sent successfully via SMTP to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email via SMTP to {to_email}: {str(e)}")
        return False


def send_email(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
    """
    Send an email using the best available method
    Tries Resend API first, falls back to SMTP if needed
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email body
        text_content: Plain text fallback (optional)
    
    Returns:
        True if sent successfully, False otherwise
    """
    # Try Resend first (works on cloud platforms)
    if send_email_resend(to_email, subject, html_content, text_content):
        return True
    
    # Fall back to SMTP
    if send_email_smtp(to_email, subject, html_content, text_content):
        return True
    
    # Both methods failed
    logger.warning(f"All email methods failed for {to_email}: {subject}")
    logger.info("Configure RESEND_API_KEY or SMTP credentials to send emails")
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
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Verify Your Email</title>
</head>
<body style="margin: 0; padding: 0; background-color: #07090d; font-family: 'Segoe UI', Arial, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #07090d;">
    <tr>
      <td align="center" style="padding: 48px 24px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px;">
          
          <!-- Logo -->
          <tr>
            <td align="center" style="padding-bottom: 6px;">
              <h1 style="font-size: 38px; font-weight: 700; letter-spacing: 1px; color: #e5e7eb; margin: 0; text-shadow: 0 0 14px rgba(120, 160, 255, 0.25);">FailState</h1>
            </td>
          </tr>
          
          <!-- Tagline -->
          <tr>
            <td align="center" style="padding-bottom: 44px;">
              <p style="font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #9ca3af; margin: 0;">VERIFICATION REQUIRED</p>
            </td>
          </tr>
          
          <!-- Main Panel -->
          <tr>
            <td style="background-color: #101218; border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 32px;">
              
              <h2 style="font-size: 22px; color: #e5e7eb; margin: 0 0 18px 0; font-weight: 600; letter-spacing: 0.5px;">Verify Your Email Address</h2>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                Hello {username},
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                Before you can access the system, you must verify your email address.
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                This ensures that records are tied to verified accounts. This prevents noise. This maintains integrity.
              </p>
              
              <!-- Divider -->
              <div style="height: 1px; background: linear-gradient(to right, transparent, rgba(255,255,255,0.12), transparent); margin: 32px 0;"></div>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                Click the button below to verify your email and activate your account:
              </p>
              
              <!-- CTA Button -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top: 28px;">
                <tr>
                  <td align="center">
                    <a href="{verification_link}" style="display: inline-block; padding: 15px 40px; background: linear-gradient(135deg, #5a82ff, #78aaff); border-radius: 12px; color: #ffffff; text-decoration: none; letter-spacing: 2px; font-size: 12px; text-transform: uppercase; font-weight: 600;">VERIFY EMAIL</a>
                  </td>
                </tr>
              </table>
              
              <!-- Divider -->
              <div style="height: 1px; background: linear-gradient(to right, transparent, rgba(255,255,255,0.12), transparent); margin: 32px 0;"></div>
              
              <p style="font-size: 12px; color: #6b7280; margin: 0 0 12px 0;">
                If the button doesn't work, copy and paste this link into your browser:
              </p>
              <p style="font-size: 11px; color: #78a0ff; word-break: break-all; margin: 0 0 18px 0;">
                {verification_link}
              </p>
              
              <!-- Divider -->
              <div style="height: 1px; background: linear-gradient(to right, transparent, rgba(255,255,255,0.12), transparent); margin: 32px 0;"></div>
              
              <p style="font-size: 12px; color: #9ca3af; margin: 0;">
                This link will expire in 24 hours.
              </p>
              
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td align="center" style="padding-top: 44px;">
              <p style="font-size: 11px; color: #6b7280; line-height: 1.6; margin: 0;">
                This message was generated by the FailState System.<br/>
                You are receiving this because you requested to create an account.<br/>
                If you did not create this account, you may safely ignore this email.
              </p>
            </td>
          </tr>
          
        </table>
      </td>
    </tr>
  </table>
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
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Access Granted</title>
</head>
<body style="margin: 0; padding: 0; background-color: #07090d; font-family: 'Segoe UI', Arial, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #07090d;">
    <tr>
      <td align="center" style="padding: 48px 24px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px;">
          
          <!-- Logo -->
          <tr>
            <td align="center" style="padding-bottom: 6px;">
              <h1 style="font-size: 38px; font-weight: 700; letter-spacing: 1px; color: #e5e7eb; margin: 0; text-shadow: 0 0 14px rgba(120, 160, 255, 0.25);">FailState</h1>
            </td>
          </tr>
          
          <!-- Tagline -->
          <tr>
            <td align="center" style="padding-bottom: 44px;">
              <p style="font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #9ca3af; margin: 0;">STILL BROKEN. STILL HERE.</p>
            </td>
          </tr>
          
          <!-- Main Panel -->
          <tr>
            <td style="background-color: #101218; border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 32px;">
              
              <h2 style="font-size: 22px; color: #e5e7eb; margin: 0 0 18px 0; font-weight: 600; letter-spacing: 0.5px;">Access Granted</h2>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                You have entered the system.
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                This platform exists because too many things remain broken — long after they were noticed, long after they were reported, long after they were meant to be fixed.
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                Most of these failures fade. They are forgotten. They are buried under newer problems.
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                Not here.
              </p>
              
              <!-- Divider -->
              <div style="height: 1px; background: linear-gradient(to right, transparent, rgba(255,255,255,0.12), transparent); margin: 32px 0;"></div>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                When you log an issue, it becomes a record. It is timestamped. It is mapped. It is archived.
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                And it is not kept silent.
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                The system automatically notifies the authorities responsible for the region. If nothing changes, the system reminds them. If nothing changes again, the record remains.
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                This does not guarantee resolution. It guarantees that unresolved things become difficult to erase.
              </p>
              
              <!-- Divider -->
              <div style="height: 1px; background: linear-gradient(to right, transparent, rgba(255,255,255,0.12), transparent); margin: 32px 0;"></div>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                We do not argue. We do not persuade. We do not forget.
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                We observe. We record. We persist.
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                What you submit will remain visible. What remains unfixed will remain visible.
              </p>
              
              <!-- Divider -->
              <div style="height: 1px; background: linear-gradient(to right, transparent, rgba(255,255,255,0.12), transparent); margin: 32px 0;"></div>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                This is not a helpdesk. This is not a promise. This is not a complaint box.
              </p>
              
              <p style="font-size: 14px; line-height: 1.75; color: #b5b9c5; margin: 0 0 18px 0;">
                This is a memory system for things that were easier to ignore.
              </p>
              
              <!-- CTA Button -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top: 28px;">
                <tr>
                  <td align="center">
                    <a href="{login_link}" style="display: inline-block; padding: 15px 40px; background: linear-gradient(135deg, #5a82ff, #78aaff); border-radius: 12px; color: #ffffff; text-decoration: none; letter-spacing: 2px; font-size: 12px; text-transform: uppercase; font-weight: 600;">ENTER SYSTEM</a>
                  </td>
                </tr>
              </table>
              
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td align="center" style="padding-top: 44px;">
              <p style="font-size: 11px; color: #6b7280; line-height: 1.6; margin: 0;">
                This message was generated by the FailState System.<br/>
                You are receiving this because you created an account.<br/>
                Records do not decay.
              </p>
            </td>
          </tr>
          
        </table>
      </td>
    </tr>
  </table>
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

