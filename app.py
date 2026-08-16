from flask import Flask

app = Flask(__name__)

my_string_variable = "Hello from Flask!"

@app.route('/my-string', methods=['GET'])
def get_my_string():
    return my_string_variable

if __name__ == '__main__':
    app.run(debug=True)
