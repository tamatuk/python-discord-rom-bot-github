import os


def now(tz=None):
    from datetime import datetime
    return datetime.now(tz)


def try_int(content, error_value=None):
    try:
        return int(content.strip())
    except ValueError:
        return error_value


def json_from_url(url):
    from requests import get
    return get(url).text


def data_from_json(json):
    from json import loads
    return loads(json)


def data_from_url(url):
    return data_from_json(json_from_url(url))


def get_workbook(credentials_file_path, workbook_id):
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_file_path, scope)
    gsheets_client = gspread.authorize(credentials)
    workbook = gsheets_client.open_by_url('https://docs.google.com/spreadsheets/d/'+workbook_id)
    return workbook


def get_worksheet(credentials_file_path, workbook_id, worksheet_name):
    workbook = get_workbook(credentials_file_path, workbook_id)
    worksheet = workbook.worksheet(worksheet_name)
    return worksheet


def df_from_gsheets_worksheet(worksheet):
    import pandas as pd
    import numpy as np
    data = worksheet.get_all_values()
    if not data:
        return None
    headers = data.pop(0)
    df = pd.DataFrame(data, columns=headers)
    df = df.replace(r'^\s*$', np.nan, regex=True)
    return df


def current_module_dir_path():
    path = os.path.abspath(__file__)
    return os.path.dirname(path)


def author_mention(ctx):
    return ctx.message.author.mention.replace("!", "")


if __name__ == "__main__":
    pass
