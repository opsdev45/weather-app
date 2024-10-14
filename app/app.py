from flask import Flask, render_template, request, redirect, url_for, make_response, send_file
from modules import backend as b
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Counter, Histogram
from functools import wraps
import time

app = Flask(__name__)

# Create app logger
b.logger(app)

# Create metrics
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})

REQUEST_COUNT = Counter(
    'app_request_count',
    'Application Request Count',
    ['method', 'endpoint', 'http_status']
)
REQUEST_LATENCY = Histogram(
    'app_request_latency_seconds',
    'Application Request Latency',
    ['method', 'endpoint']
)
# Create a new Counter to track the number of times each city has been looked at
CITY_LOOKUP_COUNT = Counter(
    'city_lookup_count',
    'Count of how many times a city has been looked up',
    ['city']
)


def track_metrics(func):
    """Decorator to track metrics for each route."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        response = func(*args, **kwargs)
        request_latency = time.time() - start_time

        # Ensure response is a Response object
        if isinstance(response, str):
            response = make_response(response)

        # Increment the request count
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.path,
            http_status=response.status_code
        ).inc()

        # Observe the request latency
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.path
        ).observe(request_latency)

        return response
    return wrapper


@app.route('/', methods=["POST", "GET"])
@track_metrics
def home():
    err = None
    if request.method == "POST":
        location = request.form.get("location").lower()

        user_ip = request.remote_addr  # Get the user's IP address
        app.logger.info(f"User with IP {user_ip} searched for weather in {location}")

        # Check if filter file is created
        if b.check_cache(location):
            b.record_location(location)
            return redirect(url_for(".display", location=location))

        json_data = b.get_api(location)
        # Check the user input
        if not json_data:
            err = " Invalid location"
            return render_template('home.html', err=err)
        else:
            b.record_location(location)
            # Create and send json file to display page
            json_f = b.filter_api(json_data)
            location = json_f[1]
            file_name = location.split(',')[0].lower()
            b.create_json_file(json_f[0], file_name)
            return redirect(url_for(".display", location=location))

    return render_template('home.html', err=err, color=b.color)


@app.route('/display/<string:location>', methods=["POST", "GET"])
@track_metrics
def display(location):
    try:
        app.logger.info(f"Weather data for {location} displayed on display page")
        CITY_LOOKUP_COUNT.labels(city=location).inc()

        file_name = f"{location.split(',')[0]}.json".lower()

        if request.method == "POST":
            return redirect(url_for(".send_db", file=file_name))

        msg = b.load_json_data(file_name)
        if not msg:
            app.logger.error(f"Failed to load JSON data for {location}")
            return render_template('error.html', error_message="Could not load weather data.")
        # take the hottest day in the week
        day = msg.get("hottest")
        msg.pop("hottest")

        return render_template("display.html", msg=msg, day=day, location=location)
    except Exception as e:
        app.logger.error(f"An error occurred while displaying weather data for {location}: {e}")

        return render_template('error.html', error_message="An unexpected error occurred.")


@app.route('/history')
def history():
    """

    """
    msg = b.load_json_data("history.json")
    return render_template("history.html", msg=msg)


@app.route('/history/d')
def history_d():
    """

    """
    return send_file("history.json", as_attachment=True)


@app.route('/download')
def download():
    try:
        b.download_from_s3()
        return redirect(url_for(".home"))
    except Exception as e:
        app.logger.error(f"An error occurred during download: {e}")
        return render_template('error.html', error_message="Download failed. Please try again.")


@app.route('/send_db/<string:file>')
def send_db(file):
    try:
        data = b.load_json_data(file)
        b.send_json_to_db(data)
        return redirect(url_for(".home"))
    except Exception as e:
        app.logger.error(f"An error occurred while sending data to DB: {e}")
        return render_template('error.html', error_message="Failed to send data to the database.")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)



