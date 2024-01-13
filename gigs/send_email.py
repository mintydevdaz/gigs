import logging
import os
import smtplib
from datetime import datetime, time
from email.message import EmailMessage

from dotenv import load_dotenv

from gigs.CONTACTS import CONTACTS
from gigs.utils import logger, save_path, timer


class MailClient:
    def __init__(self) -> None:
        load_dotenv()
        self._sender = str(os.getenv("SENDER"))
        self._password = str(os.getenv("PASSWORD"))
        self._csv_file = save_path("gigs/data_files", "annual_gigs.csv")
        self._html_text_file = save_path("gigs/data_files", "html.txt")
        self.contacts = CONTACTS["test"]  # ! toggle -> test / actual
        self.month = self._current_month()
        self.subject = self._create_subject()
        self.greeting = self._create_greeting()
        self.html_table = self._open_text_file()

    def _current_month(self) -> str:
        return datetime.now().strftime("%B")

    def _create_subject(self) -> str:
        return f"Gigs ~ {self.month}"

    def _create_greeting(self) -> str:
        now = datetime.now().time()
        midday = time(12, 0, 0)
        evening = time(18, 0, 0)
        if now < midday:
            return "Good morning"
        elif now < evening:
            return "Good afternoon"
        else:
            return "Good evening"

    def _open_text_file(self) -> str:
        with open(self._html_text_file, "r") as f:
            text = f.read()
        return text

    def _build_email_body(
        self, name: str, greeting: str, month: str, table: str
    ) -> str:
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

    def postman(self):
        with smtplib.SMTP(host="smtp.gmail.com", port=587) as server:
            server.starttls()
            server.login(user=self._sender, password=self._password)
            logging.warning("Logged into Gmail ~ sending emails...")

            for name, client_email in self.contacts.items():
                body_text = self._build_email_body(
                    name, self.greeting, self.month, self.html_table
                )

                msg = EmailMessage()
                msg["From"] = self._sender
                msg["To"] = client_email
                msg["Subject"] = self.subject
                msg.set_content(body_text, subtype="html")
                with open(self._csv_file, "rb") as f:
                    content = f.read()
                    msg.add_attachment(
                        content,
                        maintype="application",
                        subtype="csv",
                        filename="annual_gigs.csv",
                    )
                server.send_message(msg)
                logging.warning(f"-> {name} ~ {client_email}")


@timer
@logger(filepath=save_path("gigs/data", "app.log"))
def send_email():
    logging.warning(f"Running {os.path.basename(__file__)}")
    mail = MailClient()
    mail.postman()


if __name__ == "__main__":
    send_email()
