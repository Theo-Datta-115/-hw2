from flask import Flask, render_template, request, jsonify
from num2words import num2words
from text2digits import text2digits
import base64
import re

app = Flask(__name__)


t2d = text2digits.Text2Digits()

def text_to_number(text):
    """Convert English text number to integer (via text2digits)"""
    if text is None:
        raise ValueError("Unable to convert text to number")

    # normalize & keep letters/spaces/hyphens for cases like "forty-two"
    s = re.sub(r'[^a-zA-Z\s-]', '', str(text).lower()).strip()
    s = re.sub(r'-$', '', s)  # tolerate trailing hyphen: "seven-"
    if s == 'nil':
        s = 'zero'

    # convert words → digits; expect a single integer token
    converted = t2d.convert(s).strip()

    if re.fullmatch(r'[+-]?\d+', converted):
        return int(converted)

    raise ValueError("Unable to convert text to number")

def number_to_text(number):
    """Convert integer to English text"""
    try:
        return num2words(number)
    except:
        raise ValueError("Unable to convert number to text")

def base64_to_number(b64_str):
    """Convert base64 to integer"""
    try:
        # Decode base64 to bytes, then convert bytes to integer
        decoded_bytes = base64.b64decode(b64_str)
        return int.from_bytes(decoded_bytes, byteorder='big')
    except:
        raise ValueError("Invalid base64 input")

def number_to_base64(number):
    """Convert integer to base64"""
    try:
        # Convert integer to bytes, then encode to base64
        byte_count = (number.bit_length() + 7) // 8
        number_bytes = number.to_bytes(byte_count, byteorder='big')
        return base64.b64encode(number_bytes).decode('utf-8')
    except:
        raise ValueError("Unable to convert to base64")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    try:
        data = request.get_json()
        input_value = data['input']
        input_type = data['inputType']
        output_type = data['outputType']
        
        # Convert input to integer based on input type
        if input_type == 'text':
            number = text_to_number(input_value)
        elif input_type == 'binary':
            number = int(input_value, 2)
        elif input_type == 'octal':
            number = int(input_value, 8)
        elif input_type == 'decimal':
            number = int(input_value)
        elif input_type == 'hexadecimal':
            number = int(input_value, 16)
        elif input_type == 'base64':
            number = base64_to_number(input_value)
        else:
            raise ValueError("Invalid input type")
            
        # Convert integer to output type
        if output_type == 'text':
            result = number_to_text(number)
        elif output_type == 'binary':
            result = bin(number)[2:]  # Remove '0b' prefix
        elif output_type == 'octal':
            result = oct(number)[2:]  # Remove '0o' prefix
        elif output_type == 'decimal':
            result = str(number)
        elif output_type == 'hexadecimal':
            result = hex(number)[2:]  # Remove '0x' prefix
        elif output_type == 'base64':
            result = number_to_base64(number)
        else:
            raise ValueError("Invalid output type")
            
        return jsonify({'result': result, 'error': None})
    except Exception as e:
        return jsonify({'result': None, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
