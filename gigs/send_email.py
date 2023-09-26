import logging
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, time

from dotenv import load_dotenv
from gigs.CONTACTS import CONTACTS
from gigs.utils import logger, save_path, timer


def open_text_file(filepath: str) -> str:
    """
    Reads the contents of a file and returns it as a string.

    This function takes a file path as input, opens the file in read mode, reads its
    contents, and returns the contents as a string.

    Args:
        filepath (str): The path to the file.

    Returns:
        str: The contents of the file as a string.
    """
    with open(filepath, "r") as f:
        text = f.read()
    return text


def salutation(now: time) -> str:
    midday = time(12, 0, 0)
    evening = time(18, 0, 0)
    if now < midday:
        return "Good morning"
    elif now < evening:
        return "Good afternoon"
    else:
        return "Good evening"


def current_month(now: datetime) -> str:
    return now.strftime("%B")


def create_subject(month: str) -> str:
    return f"Gigs ~ {month}"


def build_html_body(name: str, greeting: str, month: str, table: str):
    return f"""
<!DOCTYPE html>
<html>
    <body style='font-family: Helvetica, Arial, sans-serif; font-size: 14px;'>
        <p>{greeting} {name},</p>
        <p>Below is the list of gigs for the next 30 days, starting in {month}.
        Attached is a more comprehensive list for the next year. You may find more gigs
        here:</p>
            <ul>
                <li><a href="https://sydneymusic.net">Sydney Music</a></li>
            </ul>
        <p>Let me know if there are others interested in receiving this email!</p>
        <p>Love,<br>Daz</p>
        <br>
        {table}
    </body>
</html>
"""


def create_email(
    server,
    from_email: str,
    to_email: str,
    subject: str,
    greeting: str,
    name: str,
    month: str,
    table: str,
    attachment_fp: str,
) -> None:
    body_text = build_html_body(name, greeting, month, table)

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text, subtype="html")

    with open(attachment_fp, "rb") as f:
        content = f.read()
        msg.add_attachment(
            content, maintype="application", subtype="csv", filename="annual_gigs.csv"
        )
    server.send_message(msg)


@timer
@logger(filepath=save_path("gigs/data", "app.log"))
def send_email():
    load_dotenv()
    SENDER = str(os.getenv("SENDER"))
    PASSWORD = str(os.getenv("PASSWORD"))

    # Load Variables
    month = current_month(now=datetime.now())
    subject = create_subject(month)
    greeting = salutation(now=datetime.now().time())
    table = open_text_file(filepath=save_path("gigs/data_files", "html.txt"))
    contacts = CONTACTS["actual"]
    csv_file = save_path("gigs/data_files", "annual_gigs.csv")

    # Send emails
    with smtplib.SMTP(host="smtp.gmail.com", port=587) as server:
        server.starttls()
        server.login(user=SENDER, password=PASSWORD)
        logging.warning("Logged into Gmail Account. Sending emails...")

        for name, client_email in contacts.items():
            create_email(
                server,
                from_email=SENDER,
                to_email=client_email,
                subject=subject,
                greeting=greeting,
                name=name,
                month=month,
                table=table,
                attachment_fp=csv_file,
            )
            logging.warning(f"-> {name} ~ {client_email}")


if __name__ == "__main__":
    send_email()
