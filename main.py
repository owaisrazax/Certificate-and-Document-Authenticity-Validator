import sqlite3
import os
import hashlib
import qrcode
import cv2
from pyzbar.pyzbar import decode as pyzbar_decode
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
import numpy as np

#CONSTANTS 
UPLOAD_FOLDER = 'uploads'
GENERATED_FOLDER = 'generated_certs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

#DATABASE 
def init_database():
    conn = sqlite3.connect('certificates.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            course_name TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            data_hash TEXT NOT NULL UNIQUE
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

#FLASK 
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GENERATED_FOLDER'] = GENERATED_FOLDER

#HELPER FUNCTIONS 
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def string_to_binary(data):
    """Convert string to binary representation."""
    binary = ''.join(format(ord(char), '08b') for char in data)
    return binary


def binary_to_string(binary):
    """Convert binary back to string."""
    result = ""
    for i in range(0, len(binary), 8):
        byte = binary[i:i+8]
        if len(byte) == 8:
            result += chr(int(byte, 2))
    return result


def embed_lsb(image, secret_data):
    #Prepared the data with markers
    header = "<<<START>>>"
    footer = "<<<END>>>"
    full_data = header + secret_data + footer
    
    #Converting to binary
    binary_data = string_to_binary(full_data)
    data_length = len(binary_data)
    
    print(f"Data to embed: {len(secret_data)} characters")
    print(f"Binary length: {data_length} bits")
    
    #image as numpy array
    img_array = np.array(image)
    height, width, channels = img_array.shape
    
    max_bytes = height * width * channels
    print(f"Image capacity: {max_bytes} bits")
    
    if data_length > max_bytes:
        raise ValueError("Image too small to embed data!")
    
    #Flatten the image array
    flat_img = img_array.flatten()
    
    # Embed data into LSB
    data_index = 0
    for i in range(len(flat_img)):
        if data_index < data_length:
            # Replace LSB with our data bit
            flat_img[i] = (flat_img[i] & 0xFE) | int(binary_data[data_index])
            data_index += 1
        else:
            break
    
    # Reshape back to image
    embedded_img = flat_img.reshape((height, width, channels))
    
    print(f"✓ Embedded {data_index} bits successfully")
    
    return Image.fromarray(embedded_img.astype('uint8'))


def extract_lsb(image):
    """
    Advanced LSB extraction - extracts from all color channels.
    Looks for header and footer markers.
    """
    # Get image 
    img_array = np.array(image)
    
    # Flattening the image
    flat_img = img_array.flatten()
    
    #Extracting LSB
    binary_data = ""
    for pixel_value in flat_img:
        binary_data += str(pixel_value & 1)
    
    #Convert binary to string
    extracted_text = binary_to_string(binary_data)
    
   
    header = "<<<START>>>"
    footer = "<<<END>>>"
    
    try:
        start_idx = extracted_text.index(header)
        end_idx = extracted_text.index(footer, start_idx)
        
        #Extract the data between markers
        actual_data = extracted_text[start_idx + len(header):end_idx]
        
        print(f"✓ Extracted data: {len(actual_data)} characters")
        return actual_data
    
    except ValueError:
        print("✗ Could not find data markers")
        return None


#ROUTES

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/create', methods=['GET', 'POST'])
def create_certificate():
    if request.method == 'POST':
        student_name = request.form['student_name']
        course_name = request.form['course_name']
        issue_date = request.form['issue_date']
        
        if 'certificate_image' not in request.files:
            return "Error: No file part in request", 400
        file = request.files['certificate_image']
        
        if file.filename == '':
            return "Error: No selected file", 400
            
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            original_filepath = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
            file.save(original_filepath)

            #Creating hash
            metadata_string = f"{student_name}|{course_name}|{issue_date}"
            data_hash = hashlib.sha256(metadata_string.encode()).hexdigest()
            
            print("\n" + "="*60)
            print("CERTIFICATE CREATION")
            print("="*60)
            print(f"Student: {student_name}")
            print(f"Course: {course_name}")
            print(f"Date: {issue_date}")
            print(f"Hash: {data_hash}")

            #Save to database
            conn = sqlite3.connect('certificates.db')
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO certificates (student_name, course_name, issue_date, data_hash) VALUES (?, ?, ?, ?)",
                    (student_name, course_name, issue_date, data_hash)
                )
                conn.commit()
                print("✓ Saved to database")
            except sqlite3.IntegrityError:
                conn.close()
                return "Error: A certificate with this exact data already exists.", 400
            except Exception as e:
                conn.close()
                return f"An error occurred: {e}", 500
            finally:
                conn.close()

            try:
                #Open cert img 
                cert_img = Image.open(original_filepath).convert('RGB')
                print(f"Original image size: {cert_img.size}")
                
                #Embed the hash using LSB
                watermarked_img = embed_lsb(cert_img, data_hash)
                
                #Save
                base_name = os.path.splitext(original_filename)[0]
                generated_filename = f"secured_{base_name}.png"
                generated_filepath = os.path.join(app.config['GENERATED_FOLDER'], generated_filename)
                watermarked_img.save(generated_filepath, 'PNG')
                
                print(f"✓ Watermarked certificate saved: {generated_filename}")
                print("="*60 + "\n")

            except Exception as e:
                import traceback
                traceback.print_exc()
                return f"Error processing image: {e}", 500

            return redirect(url_for('show_result', filename=generated_filename))
        
        else:
            return "Error: Invalid file type", 400

    return render_template('create.html')


@app.route('/result/<filename>')
def show_result(filename):
    return render_template('download.html', filename=filename)


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['GENERATED_FOLDER'], filename, as_attachment=True)


@app.route('/verify', methods=['GET', 'POST'])
def verify_certificate():
    if request.method == 'POST':
        if 'certificate_image' not in request.files:
            return "Error: No file part in request", 400
        file = request.files['certificate_image']

        if file.filename == '':
            return "Error: No selected file", 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            try:
                print("\n" + "="*60)
                print("VERIFICATION STARTED")
                print("="*60)
                
                # Open image
                cert_img = Image.open(filepath).convert('RGB')
                print(f"Image size: {cert_img.size}")
                
                # Extract hidden data
                print("\nExtracting embedded data...")
                extracted_hash = extract_lsb(cert_img)
                
                if not extracted_hash:
                    print("✗ RESULT: INVALID - No hidden data found")
                    print("="*60 + "\n")
                    result_data = {
                        "is_valid": False,
                        "error": "No authentication watermark found. This certificate may be forged or corrupted."
                    }
                    return render_template('verify_result.html', verification_data=result_data)
                
                #Verify 
                if len(extracted_hash) != 64 or not all(c in '0123456789abcdef' for c in extracted_hash):
                    print(f"✗ Invalid hash format: {extracted_hash[:32]}...")
                    print("="*60 + "\n")
                    result_data = {
                        "is_valid": False,
                        "error": "Extracted data is corrupted or invalid."
                    }
                    return render_template('verify_result.html', verification_data=result_data)
                
                print(f"Extracted hash: {extracted_hash}")
                
                #Check against database
                print("\nQuerying database...")
                conn = sqlite3.connect('certificates.db')
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT student_name, course_name, issue_date FROM certificates WHERE data_hash = ?",
                    (extracted_hash,)
                )
                record = cursor.fetchone()
                conn.close()

                if record:
                    print("✓ RESULT: VALID - Certificate authenticated!")
                    print(f"  Student: {record[0]}")
                    print(f"  Course: {record[1]}")
                    print(f"  Date: {record[2]}")
                    print("="*60 + "\n")
                    
                    result_data = {
                        "is_valid": True,
                        "student_name": record[0],
                        "course_name": record[1],
                        "issue_date": record[2]
                    }
                else:
                    print("✗ RESULT: INVALID - Hash not registered in database")
                    print("="*60 + "\n")
                    
                    result_data = {
                        "is_valid": False,
                        "error": "Watermark found but not registered in our database. This certificate is not authentic."
                    }
                
                return render_template('verify_result.html', verification_data=result_data)

            except Exception as e:
                print(f"✗ ERROR: {e}")
                import traceback
                traceback.print_exc()
                result_data = {"is_valid": False, "error": f"Error during verification: {e}"}
                return render_template('verify_result.html', verification_data=result_data)
        
        else:
            return "Error: Invalid file type", 400

    return render_template('verify.html')


if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(GENERATED_FOLDER, exist_ok=True)
    init_database()
    app.run(debug=True)
