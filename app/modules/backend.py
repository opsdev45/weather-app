import json
import requests
import os
import datetime
from dotenv import load_dotenv
import re
from deep_translator import GoogleTranslator
from boto3.session import Session
import boto3
import logging
from logging.handlers import TimedRotatingFileHandler


# load the env

load_dotenv()
cache = os.getenv("cache")
API_KEY = os.getenv("API_KEY")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
color = os.getenv("BG_COLOR")


def check_cache(user_input):
    """Return the path to json file if exist in cache,False otherwise """

    # remove all the oldest file
    delete()
    files = os.listdir(cache)
    json_f = user_input + ".json"
    if json_f in files:
        return True

    return False


def get_api(user_input):
    """Return Raw json data , otherwise False"""
    response = requests.request("GET",
                                f'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{user_input}/?unitGroup=metric&elements=datetime%2CdatetimeEpoch%2Ctempmax%2Ctempmin%2Ctemp%2Chumidity&include=days%2Chours&key={API_KEY}&contentType=json')
    # Not found the location
    if response.status_code != 200:
        return False

    return response


def filter_api(json_data):
    """Filter weather as json Return json and location in english"""

    json_data = json_data.json()
    data = json_data.get('days')
    city = json_data['resolvedAddress']
    # if not english translate
    if not re.search("[a-z]", city):
        city = GoogleTranslator(source='auto', target='en').translate(city)

    result = {}
    i = 0
    for day_data in data[:7]:
        # Process the first 7 days (if available)
        morning = day_data.get("hours")[10].get('temp')
        evening = day_data.get("hours")[22].get('temp')
        datetime = day_data.get('datetime')
        humidity = day_data.get('humidity')

        # Check if the data is in json and add to json
        if datetime and morning and evening and humidity:
            result.update({f"day{i+1}": {
                'datetime': datetime,
                'temp_morning': morning,
                'temp_evening': evening,
                'humidity': humidity
            }})
        i += 1
    return result, city


def create_json_file(json_filter, location):
    """Return json file with weather filter"""
    day = hottest_day(json_filter)
    json_filter.update({"hottest": day})

    # Create json file
    file = f"{cache}{location}.json"
    with open(file, "w") as j:
        json.dump(json_filter, j)


def delete():
    """Delete file after day and the oldest file if needed"""

    today = datetime.datetime.now()

    # sort the folder by time
    files = os.listdir(cache)
    files = [os.path.join(cache, x) for x in files]
    files = sorted(files, key=os.path.getmtime)

    for file in files:
        # get the days of file
        file_date = datetime.datetime.fromtimestamp(os.path.getctime(file))
        num = (today - file_date).days

        oldest_file = files[0]

        # delete file after one day
        if num >= 1:
            os.remove(file)

        # delete the oldest file after 10 files
        if len(files) >= 10:
            os.remove(oldest_file)
            files.remove(oldest_file)


def hottest_day(json_file):
    """Return the hottest day in the week"""
    max_temp = 0
    day = -1
    for key, val in json_file.items():
        temp = (val.get("temp_morning") + val.get("temp_evening") // 2)
        if max_temp < temp:
            max_temp = temp
            day = key
    return day


def load_json_data(file_name):
    if file_name == "history.json":
        path_json = f"history/{file_name}"
    else:
        path_json = f"{cache}{file_name}"
    if path_json:
        with open(path_json, "r") as f:
            data = json.load(f)
        return data


def record_location(location):
    entry = {
        "time": str(datetime.datetime.now()),
        "location": location
    }

    try:
        with open("history/history.json", "r") as f:
            history = json.load(f)
    except:
        history = []

    history.append(entry)

    # Write the updated history back to the file
    with open("history/history.json", "w") as f:
        json.dump(history, f)


def download_from_s3():
    """Connect and download image from s3 bucket aws"""
    session = Session(aws_access_key_id=ACCESS_KEY,
                      aws_secret_access_key=SECRET_KEY)

    s3 = session.resource('s3')
    desktop = os.path.normpath(os.path.expanduser("~/Desktop"))

    s3.Bucket("app-bucket-ofir").download_file("image.jpg", f'{desktop}/image.jpg')


def send_json_to_db(jsondata):
    """Upload json to dynamodb aws"""
    # convert json to str
    jsondata = json.dumps(jsondata)

    database = boto3.resource('dynamodb',
                              region_name='us-east-1',
                              aws_access_key_id=ACCESS_KEY,
                              aws_secret_access_key=SECRET_KEY)
    key_db = "weatherApp_key"
    table = database.Table("DB_weatherApp")
    table.put_item(Item={key_db: jsondata})


def logger(app):
    """
    Configures logging for the Flask application using TimedRotatingFileHandler.

    Args:
        app (Flask): The Flask application instance.
    """
    # Create a TimedRotatingFileHandler
    log_handler = TimedRotatingFileHandler(
        filename='logs/weather_app.log',  # Base filename for log files
        when='midnight',             # Rotate log file at midnight
        interval=1,                  # The interval of logging rotation (1 day)
        backupCount=7                # Number of backup files to keep
    )

    log_handler.suffix = "%Y-%m-%d"  # Date format for log file names
    log_handler.setLevel(logging.INFO)  # Capture all logs of INFO level and above
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_handler.setFormatter(formatter)

    # Add the handler to the Flask app's logger
    app.logger.addHandler(log_handler)
    app.logger.setLevel(logging.INFO)



