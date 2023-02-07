import smtplib
from pathlib import Path

from contacts import test_contact
from dotenv import load_dotenv
from email_body import (
    create_email_message,
    delete_csv,
    file_attachment,
    html_body,
    html_table,
    plain_body,
)


def main():
    # Create path to Desktop. Filename vars.
    dir_path = str(Path.home() / "Desktop")
    fp_gigs = f"{dir_path}/gigs.csv"
    fp_pretty = f"{dir_path}/pretty_table.csv"

    # Environment Vars
    load_dotenv(dotenv_path=os.path.basename("gigs/.env"))
    SENDER = os.getenv("SENDER")
    PASSWORD = os.getenv("PASSWORD")

    # Prepare email attachment
    attachment = file_attachment(fp_gigs)

    # Create HTML table
    table = html_table(file_path=fp_pretty)

    # Login to Gmail Account
    SERVER_ADDRESS = "smtp.gmail.com"
    TLS_PORT = 587
    with smtplib.SMTP(SERVER_ADDRESS, TLS_PORT) as server:
        server.starttls()
        server.login(SENDER, PASSWORD)

        # Get each contact in contacts list
        for name, receiver in test_contact.items():
            print(f"Preparing email for {name} ({receiver})")

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
    delete_csv(fp_gigs, fp_pretty)


if __name__ == "__main__":
    main()
