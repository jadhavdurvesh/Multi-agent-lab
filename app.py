from flask import Flask

app = Flask(__name__)

# Define a string variable
my_string_variable = "Hello, Flask World!"

@app.route('/my-string', methods=['GET'])
def get_my_string():
    """
    Returns the value of the my_string_variable.
    """
    return my_string_variable

if __name__ == '__main__':
    app.run(debug=True)
