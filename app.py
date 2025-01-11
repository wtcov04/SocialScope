from flask import Flask, render_template, request, redirect, url_for, flash, session
import firebase_admin
from firebase_admin import credentials, auth
import requests

app = Flask(__name__)
app.secret_key = 'e33d2f3c993db5c91c04f16cd344b61e'  # Your secret key for flash messages and session management

# Initialize Firebase Admin SDK
cred = credentials.Certificate('firebase_credentials.json')  # Path to your Firebase private key file
firebase_admin.initialize_app(cred)

@app.route('/')
def home():
    # This is the first page that will load with options to login or sign up
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            # Create a new user in Firebase
            user = auth.create_user(
                email=email,
                password=password
            )
            flash("Account created successfully! Please log in.")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error: {str(e)}")
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            # Log in the user (getting the user from Firebase)
            user = auth.get_user_by_email(email)
            session['user_id'] = user.uid  # Store user ID in the session
            session['user_email'] = user.email  # Store user email in the session
            flash("Logged in successfully!")
            return redirect(url_for('dashboard'))  # Redirect to the dashboard page
        except auth.AuthError as e:
            flash(f"Error: {str(e)}")  # Show any error messages (e.g., incorrect login)
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Clear the session data
    session.clear()
    # Redirect to the login page or home page
    return redirect(url_for('login'))  # Or redirect to home: return redirect(url_for('home'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    # Check if user is logged in
    if 'user_id' not in session:
        flash("You must log in to search for Instagram profiles.")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        
        # Validate input
        if not username.strip():
            flash("Username cannot be empty.")
            return render_template('dashboard.html')
        
        return redirect(url_for('instagram', username=username))
    
    return render_template('dashboard.html')

@app.route('/instagram/<username>')
def instagram(username):
    # Check if user is logged in
    if 'user_id' not in session:
        flash("You must log in to view Instagram profiles.")
        return redirect(url_for('login'))

    url = "https://instagram-scraper-api2.p.rapidapi.com/v1/info"
    querystring = {"username_or_id_or_url": username}

    headers = {
        "X-RapidAPI-Key": "fd4843d805mshaeecba3856a33f7p130641jsn6678e926215d",
        "X-RapidAPI-Host": "instagram-scraper-api2.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)
        
        if response.status_code == 200:
            data = response.json()['data']

            # Fetch recent media posts (likes, comments, etc.)
            media_url = "https://instagram-scraper-api2.p.rapidapi.com/v1/media"
            media_querystring = {"username_or_id_or_url": username}
            media_response = requests.get(media_url, headers=headers, params=media_querystring)
            
            media_data = media_response.json().get('data', [])

            return render_template('instagram_profile.html', data=data, media_data=media_data)

    except requests.exceptions.RequestException as e:
        return render_template('error.html', error_message="Failed to fetch Instagram data. Please check the username or try again later.")

if __name__ == '__main__':
    app.run(debug=True)
