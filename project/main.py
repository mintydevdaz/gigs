import os
import smtplib
from pathlib import Path

import pandas as pd
from contacts import test_contact
from dotenv import load_dotenv
from email_body import create_email_message, file_attachment, html_body, plain_body
from pretty_html_table import build_table


def main():
    # Create path to Desktop. Filename vars.
    dir_path = str(Path.home() / "Desktop")
    fp_gigs = "gigs.csv"
    fp_pretty = "pretty_table.csv"

    # Environment Vars
    load_dotenv(dotenv_path=os.path.basename("gigs/.env"))
    SENDER = os.getenv("SENDER")
    PASSWORD = os.getenv("PASSWORD")

    # Prepare email attachment
    attachment = file_attachment(f"{dir_path}/{fp_gigs}")

    # Create HTML table
    table = html_table(dir_path, fp_pretty)

    # Login to Gmail Account
    SERVER_ADDRESS = "smtp.gmail.com"
    TLS_PORT = 587
    with smtplib.SMTP(SERVER_ADDRESS, TLS_PORT) as server:
        server.starttls()
        server.login(SENDER, PASSWORD)

        # Get each contact in contacts list
        for name, receiver in test_contact.items():
            # Prepare body of email
            plain_text = plain_body(name)
            html_text = html_body(name, table)

            # Create email
            msg = create_email_message(
                from_address=SENDER,
                to_address=receiver,
                body=plain_text,
                html_body=html_text,
                attachment=attachment,
                attachment_name="gigs.csv",
            )

            # Send email
            server.send_message(msg)
            print(f"-> Email sent to {name} ({receiver})")

    # Remove CSV files from Desktop
    os.remove(f"{dir_path}/{fp_gigs}")
    os.remove(f"{dir_path}/{fp_pretty}")
    print("Removed CSV files from Desktop")


def html_table(directory_path: str, filename: str) -> str:
    """Create pretty_html_table"""
    df = pd.read_csv(f"{directory_path}/{filename}")
    return build_table(
        df,
        "blue_light",
        font_family="Open Sans, sans-serif",
        text_align="left",
        width="auto",
    )


if __name__ == "__main__":
    main()
