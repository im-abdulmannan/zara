import webbrowser


def open_url(url: str) -> None:
    """Open a URL in the default web browser."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
