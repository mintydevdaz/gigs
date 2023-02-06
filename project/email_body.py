from email.message import EmailMessage


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


def plain_body(name: str) -> str:
    """Returns email body in plain text"""
    return f"""
            Dear {name},

            Attached is the current list of gigs for the following venues:

            - Big Top Luna Park
            - Enmore Theatre
            - Factory Theatre
            - Lansdowne Hotel
            - Lazybones Lounge
            - Manning Bar
            - Metro Theatre
            - Oxford Art Factory
            - Phoenix Central Park
            - Sydney Opera House
            - The Concourse
            - UNSW Roundhouse

            You might find more gigs here:
            - https://sydneymusic.net
            - https://www.ticketmaster.com.au
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
                    <p>Below is the current list of gigs for the next 30
                    days at the following venues.
                    Attached is a more comprehensive list.</p>
                        <ul>
                            <li>Big Top Luna Park</li>
                            <li>Enmore Theatre</li>
                            <li>Factory Theatre</li>
                            <li>Lansdowne Hotel</li>
                            <li>Lazybones Lounge</li>
                            <li>Manning Bar</li>
                            <li>Metro Theatre</li>
                            <li>Oxford Factory Theatre</li>
                            <li>Phoenix Central Park</li>
                            <li>Sydney Opera House</li>
                            <li>The Councourse</li>
                            <li>UNSW Roundhouse</li>
                        </ul>
                    <p>You might find more gigs here:</p>
                        <ul>
                            <li><a href="https://sydneymusic.net">Sydney Music</a></li>
                            <li><a href="https://www.ticketmaster.com.au/browse/all-music-catid-10001/music-rid-10001">Ticketmaster</a></li>
                            <li><a href="https://premier.ticketek.com.au/shows/genre.aspx?c=2048">Ticketek</a></li>
                        </ul>
                    <p>Let me know if there are others interested in receiving this email.</p>
                    {html_table}
                    <p>Kind regards,
                    <br>Darren "Cool D" Chung<p>
                </body>
            </html>
            """
