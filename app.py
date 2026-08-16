from flask import Flask

app = Flask(__name__)

MY_STRING = "Hello from Flask!"

@app.route('/my-string', methods=['GET'])
def get_my_string():
    """Returns the predefined string variable."""
    return MY_STRING

if __name__ == '__main__':
    # In a production environment, a more robust WSGI server like Gunicorn
    # or uWSGI would be used. For development, app.run() is sufficient.
    # Using debug=True provides a reloader and debugger, useful for development.
    # Host '0.0.0.0' makes the server accessible externally, helpful in containerized environments.
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"Error starting Flask application: {e}")
        # In a real application, you might log this error more formally
        # and potentially attempt to gracefully shut down or restart.
