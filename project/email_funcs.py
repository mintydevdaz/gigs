import os
import sys
from email.message import EmailMessage

import pandas as pd
from pretty_html_table import build_table


def file_attachment(csv_file: str) -> bytes:
    """Prepare CSV attachment for email(s)"""
    with open(csv_file, "rb") as content_file:
        return content_file.read()


def create_email_message(
    from_address: str,
    to_address: str,
    body: str,
    html_body: str,
    attachment: bytes,
    attachment_name: str,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_address
    msg["To"] = to_address
    msg["Subject"] = "Upcoming Gigs"
    msg.set_content(body)
    msg.set_content(html_body, subtype="html")
    msg.add_attachment(
        attachment, maintype="application", subtype="csv", filename=f"{attachment_name}"
    )
    return msg


def html_table(file_path: str) -> str:
    """Create pretty_html_table"""
    df = pd.read_csv(file_path)
    return build_table(
        df,
        "blue_light",
        font_family="Open Sans, sans-serif",
        text_align="left",
        width="auto",
    )


def delete_csv(gigs_csv: str, pretty_csv: str):
    while True:
        try:
            ans = str(
                input(
                    f"Delete files from Desktop? (y/n)\n->{gigs_csv}\n->{pretty_csv}\nInput Here: "
                )
            ).lower()
            if ans in {"y", "yes"}:
                os.remove(gigs_csv)
                os.remove(pretty_csv)
                sys.exit("Removed CSV files from Desktop")
            elif ans in {"n", "no"}:
                sys.exit("Files NOT deleted!")
            else:
                continue
        except Exception:
            continue


def plain_body(name: str) -> str:
    """Returns email body in plain text"""
    return f"""
            Dear {name},

            Attached is the current list of gigs.

            You might find more gigs here:
            - https://sydneymusic.net
            - http://m.ticketek.com.au

            Let me know if there are others interested in receiving this email.

            Kind regards,
            Darren "Cool D" Chung
            """


def html_body(name: str, html_table: str) -> str:
    return f"""\
            <!DOCTYPE html>
            <html>
                <body>
                    <p>Dear {name},</p>
                    <p>Here are the current list of gigs for the next 30
                    days. Attached is a more comprehensive list.</p>
                    <p>You might find more gigs here:</p>
                        <ul>
                            <li><a href="https://sydneymusic.net">Sydney Music</a></li>
                            <li><a href="https://premier.ticketek.com.au/shows/genre.aspx?c=2048">Ticketek</a></li>
                        </ul>
                    <p>Let me know if there are others interested in receiving this email.</p>
                    {html_table}
                    <p>Kind regards,
                    <br>Darren "Cool D" Chung<p>
                </body>
            </html>
            """
