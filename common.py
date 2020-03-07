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


def df_from_gsheets_worksheet(credentials_file_path, workbook_id, worksheet_name):
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    import pandas as pd
    import numpy as np
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_file_path, scope)
    gsheets_client = gspread.authorize(credentials)
    workbook = gsheets_client.open_by_url('https://docs.google.com/spreadsheets/d/'+workbook_id)
    worksheet = workbook.worksheet(worksheet_name)

    data = worksheet.get_all_values()
    headers = data.pop(0)
    df = pd.DataFrame(data, columns=headers)
    df = df.replace(r'^\s*$', np.nan, regex=True)
    return df


def current_module_dir_path():
    path = os.path.abspath(__file__)
    return os.path.dirname(path)


if __name__ == "__main__":
    pass
