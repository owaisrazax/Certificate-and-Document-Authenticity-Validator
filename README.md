# 🎓 Certificate And Document Authenticity Validator - My B.Tech Project

This is a web app I built using Flask and Python to create and verify digital certificates.
The main idea is to tackle the problem of fake certificates. This app embeds a secure, invisible watermark (a hash) directly into the certificate image. 
It then stores this hash in a database. If someone wants to check if a certificate is real, they just upload it, and the app will check if the watermark is valid and exists in our records.

## 🚀 How It Works

It's a simple two-part system:

### 1. Creating a Secure Certificate:
* An admin (or me, in this case) fills out a form with the student's name, course, and date.
* The app takes this data and creates a unique **SHA-256 hash** (a super secure fingerprint).
* This hash is then **invisibly embedded** into the certificate image using **LSB (Least Significant Bit) Steganography**. It basically tweaks the last bit of the color data for each pixel. You can't see the change!
* The original hash is also saved in an **SQLite database** to act as the "master record".

### 2. Verifying a Certificate:
* Anyone can upload a certificate image to the `/verify` page.
* The app automatically extracts the invisible data from the image's LSBs.
* It looks for the hidden hash (it looks for the `<<<START>>>` and `<<<END>>>` tags I added).
* If it finds a hash, it checks it against the SQLite database.
* **If the hash exists in the database:** The certificate is **Valid!** ✅
* **If the hash is missing or doesn't exist in the database:** The certificate is **Fake!** ❌

---

## 🛠️ Tech Stack

* **Backend:** Flask (for the web server and routes)
* **Database:** SQLite (super simple, file-based)
* **Image Processing & LSB:** Pillow (PIL), OpenCV (cv2), and Numpy
* **Hashing:** `hashlib` (for SHA-256)
* **Frontend:** Just plain HTML/CSS (you'll have to make your own `templates` folder)

---

## 🏃 How to Run This Project

1.  **Clone the repo:**
    ```bash
    git clone [https://github.com/](https://github.com/)[your_username]/[your_repo_name].git
    cd [your_repo_name]
    ```

2.  **Create a virtual environment (always a good idea):**
    ```bash
    # For Mac/Linux
    python3 -m venv venv
    source venv/bin/activate
    
    # For Windows
    python -m venv venv
    venv\Scripts\activate
    ```

3.  **Install the libraries:**
    (I didn't make a `requirements.txt`, so you'll have to install them manually. My bad.)
    ```bash
    pip install Flask numpy pillow opencv-python pyzbar-py3 qrcode
    ```

4.  **IMPORTANT: Create your HTML files:**
    This code *only* has the Python backend. You need to create a `templates` folder in the same directory and make these files inside it:
    * `index.html` (The home page)
    * `create.html` (The form for creating certs)
    * `download.html` (The page that links to the new cert)
    * `verify.html` (The form to upload a cert for verification)
    * `verify_result.html` (Shows if the cert is valid or fake)

5.  **Run the app:**
    The app will automatically create the `certificates.db` file and the `uploads` and `generated_certs` folders when you first run it.
    ```bash
    python app.py
    ```

6.  **Open it in your browser:**
    Go to `http://127.0.0.1:5000`
