# Ragnarok Mobile Discord Bot

Simple easy-peasy bot for Ragnarok Mobile Discord server.

## Getting Started

1. Install requirements first
   ````
   pip install -r requirements.txt
   ````

2. To Use Google API download credentials:

    Log into the [Google Developers Console](https://console.developers.google.com/) with the Google account whose 
    spreadsheets you want to access. 
    Create (or select) a project and enable the **Drive API** and **Sheets API** (under **Google Apps APIs**).

    Go to the Credentials for your project and create **New credentials > OAuth client ID >** of type **Other**. 
    In the list of your **OAuth 2.0 client IDs** click **Download JSON** for the Client ID you just created. 
    Save the file as ``client_secrets.json`` in your home directory (user directory). 
    Another file, named ``storage.json``, will be created after successful authorization to cache OAuth data.

    On you first usage, your web browser will be opened, 
    asking you to log in with your Google account to authorize this client read access to all its Google Drive files 
    and Google Sheets.

## Update Language pack

1. Run next command for file need to be updated. Update pygettext.py address according to your system settings:
    ````
   py -3.5 C:\Users\tamat\AppData\Local\Programs\Python\Python35\Tools\i18n\pygettext.py -d discord_cogs/prices discord_cogs/prices.py
   py -3.5 C:\Users\tamat\AppData\Local\Programs\Python\Python35\Tools\i18n\pygettext.py -d discord_cogs/events discord_cogs/events.py
   py -3.5 C:\Users\tamat\AppData\Local\Programs\Python\Python35\Tools\i18n\pygettext.py -d discord_cogs/attendance discord_cogs/attendance.py
    ````

2. Update .po files using Poedit
