import urllib.parse
from tools.url_opener import open_url

WEBSITES = {
    "google": "google.com",
    "youtube": "youtube.com",
    "github": "github.com",
    "gmail": "mail.google.com",
    "facebook": "facebook.com",
    "twitter": "twitter.com",
    "reddit": "reddit.com",
    "stackoverflow": "stackoverflow.com",
    "wikipedia": "wikipedia.org"
}

def open_website(site_name):
    """
    Opens a website by name or direct URL.
    Returns the resolved URL that was opened.
    """
    site_name = site_name.lower().strip()
    
    if site_name in WEBSITES:
        url = WEBSITES[site_name]
    else:
        # Fallback if domain is already specified (like wikipedia.org)
        if "." in site_name:
            url = site_name
        else:
            url = f"{site_name}.com"
            
    open_url(url)
    return url

def search_google(query):
    """
    Encodes and searches a query on Google.
    Returns the final Google search URL.
    """
    encoded_query = urllib.parse.quote(query.strip())
    url = f"https://www.google.com/search?q={encoded_query}"
    open_url(url)
    return url
