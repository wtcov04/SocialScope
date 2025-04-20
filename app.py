from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, send_file
import requests
import random
import json
import warnings
import pandas as pd
import firebase_admin
from pytrends.request import TrendReq
from firebase_admin import credentials, auth, db
from weasyprint import HTML
from matplotlib import pyplot as plt
from io import BytesIO
import base64


# Ignore certain warnings
warnings.filterwarnings("ignore", category=FutureWarning)

app = Flask(__name__)
app.secret_key = 'e33d2f3c993db5c91c04f16cd344b61e' 

FIREBASE_API_KEY = "AIzaSyBvWfBvCtN3x99L-4g9GxKEo8ep6HhqGKI" 

cred = credentials.Certificate('firebase_credentials.json') 
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://socialscope-a8af5-default-rtdb.europe-west1.firebasedatabase.app/'
})

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            user = auth.create_user(email=email, password=password)

            # Sign in using Firebase REST API to get ID token
            sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            res = requests.post(sign_in_url, data=json.dumps(payload))
            id_token = res.json().get("idToken")

            # Send verification email
            verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
            verify_payload = {
                "requestType": "VERIFY_EMAIL",
                "idToken": id_token
            }
            requests.post(verify_url, data=json.dumps(verify_payload))

            flash("Account created. A verification email has been sent to your inbox.")
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
            user = auth.get_user_by_email(email)
            if user:
                session['user_id'] = user.uid  # Store user ID in the session
                session['user_email'] = user.email  # Store email in session
                return redirect(url_for('dashboard'))  # Redirect to dashboard after login
            else:
                flash("Invalid email or password.")  # Show error for invalid login credentials
        except auth.UserNotFoundError:
            flash("No user found with that email.")  # Handle user not found error
        except Exception as e:
            flash(f"Error: {str(e)}")  # General error handler

    return render_template('login.html') 

@app.route('/logout')
def logout():
    # Clear the session data
    session.clear()
    # Redirect to the login page or home page
    return redirect(url_for('login')) 

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or 'user_email' not in session:
        flash("You must log in first.")
        return redirect(url_for('login'))

    try:
        user = auth.get_user(session['user_id'])

        if not user.email_verified:
            flash("Please verify your email before accessing the dashboard.")
            return redirect(url_for('login'))

        ref = db.reference(f"/saved_profiles/{user.uid}")
        saved_profiles = ref.get() or {}

        return render_template("dashboard.html",
                               user_email=user.email,
                               saved_profiles=saved_profiles)
    except Exception as e:
        flash("Something went wrong. Please log in again.")
        return redirect(url_for('login'))
    
@app.route('/tiktok/<username>')
def tiktok(username):
    if 'user_id' not in session:
        flash("You must log in to view TikTok profiles.")
        return redirect(url_for('login'))

    info_url = "https://tiktok-scraper7.p.rapidapi.com/user/info"
    posts_url = "https://tiktok-scraper7.p.rapidapi.com/user/posts"

    querystring = {"unique_id": username}
    headers = {
        "X-RapidAPI-Key": "fd4843d805mshaeecba3856a33f7p130641jsn6678e926215d",
        "X-RapidAPI-Host": "tiktok-scraper7.p.rapidapi.com"
    }

    try:
        # Get profile info
        info_response = requests.get(info_url, headers=headers, params=querystring)
        info_response.raise_for_status()
        full_data = info_response.json()

        user_data = full_data["data"]["user"]
        stats_data = full_data["data"]["stats"]

        # Get recent posts
        posts_response = requests.get(posts_url, headers=headers, params=querystring)
        posts_response.raise_for_status()
        posts_data = posts_response.json().get("data", {}).get("videos", [])

        # Find most liked video
        most_liked_post = None
        max_likes = -1
        for post in posts_data:
            if post.get("digg_count", 0) > max_likes:
                most_liked_post = post
                max_likes = post["digg_count"]

        # Chart Data: Likes, Views & Engagement Over Time
        video_labels = []
        likes_over_time = []
        views_over_time = []
        engagement_rate_over_time = []

        for i, post in enumerate(posts_data[:5]):
            video_labels.append(f"Video {i + 1}")
            likes = post.get("digg_count", 0)
            comments = post.get("comment_count", 0)
            shares = post.get("share_count", 0)
            views = post.get("play_count", 1)  # Prevent division by 0

            likes_over_time.append(likes)
            views_over_time.append(views)

            # Calculate engagement rate: ((likes + comments + shares) / views) * 100
            engagement = ((likes + comments + shares) / views) * 100
            engagement_rate_over_time.append(round(engagement, 2))

        likesData = {
            "labels": video_labels,
            "datasets": [{
                "label": "Likes",
                "data": likes_over_time,
                "backgroundColor": "rgba(255, 99, 132, 0.2)",
                "borderColor": "rgba(255, 99, 132, 1)",
                "borderWidth": 1
            }]
        }

        viewsData = {
            "labels": video_labels,
            "datasets": [{
                "label": "Views",
                "data": views_over_time,
                "backgroundColor": "rgba(54, 162, 235, 0.2)",
                "borderColor": "rgba(54, 162, 235, 1)",
                "borderWidth": 1
            }]
        }

        engagementRateData = {
            "labels": video_labels,
            "datasets": [{
                "label": "Engagement Rate (%)",
                "data": engagement_rate_over_time,
                "backgroundColor": "rgba(255, 206, 86, 0.2)",
                "borderColor": "rgba(255, 206, 86, 1)",
                "borderWidth": 1
            }]
        }

        followersFollowingData = {
            "labels": ["Followers", "Following"],
            "datasets": [{
                "label": "Followers vs Following",
                "data": [stats_data["followerCount"], stats_data["followingCount"]],
                "backgroundColor": ["rgba(75, 192, 192, 0.2)", "rgba(255, 206, 86, 0.2)"],
                "borderColor": ["rgba(75, 192, 192, 1)", "rgba(255, 206, 86, 1)"],
                "borderWidth": 1
            }]
        }

        return render_template(
            'tiktok_profile.html',
            user=user_data,
            stats=stats_data,
            posts=posts_data,
            most_liked=most_liked_post,
            likesData=likesData,
            viewsData=viewsData,
            engagementRateData=engagementRateData,
            followersFollowingData=followersFollowingData
        )

    except requests.exceptions.RequestException as e:
        flash("Failed to fetch TikTok data. Please try again later.")
        return render_template('error.html', error_message=str(e))
    
@app.route('/tiktok/<username>/download-report', methods=['POST'])
def download_tiktok_report(username):
    if 'user_id' not in session:
        flash("You must log in to download reports.")
        return redirect(url_for('login'))

    info_url = "https://tiktok-scraper7.p.rapidapi.com/user/info"
    posts_url = "https://tiktok-scraper7.p.rapidapi.com/user/posts"
    querystring = {"unique_id": username}
    headers = {
        "X-RapidAPI-Key": "fd4843d805mshaeecba3856a33f7p130641jsn6678e926215d",
        "X-RapidAPI-Host": "tiktok-scraper7.p.rapidapi.com"
    }

    try:
        user_info = requests.get(info_url, headers=headers, params=querystring).json()["data"]
        user = user_info["user"]
        stats = user_info["stats"]

        posts = requests.get(posts_url, headers=headers, params=querystring).json()["data"]["videos"][:5]
        labels = [f"Video {i+1}" for i in range(len(posts))]
        likes = [post.get("digg_count", 0) for post in posts]

        # Create chart image
        plt.figure(figsize=(6, 4))
        plt.bar(labels, likes, color='hotpink')
        plt.title("Likes per Video")
        plt.xlabel("Videos")
        plt.ylabel("Likes")
        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        likes_chart_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        buffer.close()
        plt.close()

        rendered = render_template("tiktok_report.html", user=user, stats=stats, likes_chart=likes_chart_base64)
        pdf = HTML(string=rendered).write_pdf()

        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=tiktok_{username}_report.pdf'
        return response

    except Exception as e:
        flash(f"Could not generate report: {str(e)}", "danger")
        return redirect(url_for('tiktok', username=username))
    
@app.route('/instagram/<username>')
def instagram(username):
    if 'user_id' not in session:
        flash("You must log in to view Instagram profiles.")
        return redirect(url_for('login'))

    info_url = "https://instagram-premium-api-2023.p.rapidapi.com/v1/user/web_profile_info"
    media_url = "https://instagram-premium-api-2023.p.rapidapi.com/v1/user/medias"

    headers = {
        "X-RapidAPI-Key": "ea25d69c86mshf20970f95219b08p17faa0jsn41578a36d0c9",
        "X-RapidAPI-Host": "instagram-premium-api-2023.p.rapidapi.com"
    }

    try:
        # Step 1: Get profile info
        profile_response = requests.get(info_url, headers=headers, params={"username": username})
        profile_response.raise_for_status()
        response_json = profile_response.json()

        user_data = response_json.get("user")
        if not user_data:
            return render_template("error.html", error_message="No Instagram profile data found.")

        # Step 2: Extract profile info
        full_name = user_data.get("full_name", "N/A")
        bio = user_data.get("biography", "")
        username = user_data.get("username", "")
        profile_pic = (
            user_data.get("profile_pic_url_hd")
            or user_data.get("profile_pic_url")
            or "/static/img/default-avatar.png"
        )
        followers = user_data.get("edge_followed_by", {}).get("count", 0)
        following = user_data.get("edge_follow", {}).get("count", 0)
        external_url = user_data.get("external_url", "")
        is_verified = user_data.get("is_verified", False)
        user_id = user_data.get("id")

        if not user_id:
            return render_template("error.html", error_message="User ID not found in profile data.")

        # Followers vs Following chart
        followersFollowingData = {
            "labels": ["Followers", "Following"],
            "datasets": [{
                "label": "Followers vs Following",
                "data": [followers, following],
                "backgroundColor": ["rgba(54, 162, 235, 0.2)", "rgba(255, 99, 132, 0.2)"],
                "borderColor": ["rgba(54, 162, 235, 1)", "rgba(255, 99, 132, 1)"],
                "borderWidth": 1
            }]
        }

        # Step 3: Get media data
        media_response = requests.get(media_url, headers=headers, params={"user_id": user_id, "amount": 6})
        media_response.raise_for_status()
        media_data_raw = media_response.json()

        if not isinstance(media_data_raw, list):
            return render_template("error.html", error_message="Instagram API returned unexpected data format.")

        media_data = media_data_raw[:6]  # Limit to 6 posts

        # Step 4: Prepare chart data
        post_labels = [f"Post {i+1}" for i in range(len(media_data))]
        likes = [post.get("like_count", 0) for post in media_data]
        comments = [post.get("comment_count", 0) for post in media_data]

        views = []
        for post in media_data:
            view_count = post.get("view_count") or post.get("play_count")
            views.append(view_count if view_count is not None else 1)  # Avoid divide-by-zero

        # Step 5: Calculate Engagement Rate
        engagement_rates = []
        for i in range(len(media_data)):
            rate = ((likes[i] + comments[i]) / views[i]) * 100
            engagement_rates.append(round(rate, 2))

        likesData = {
            "labels": post_labels,
            "datasets": [{
                "label": "Likes per Post",
                "data": likes,
                "backgroundColor": "rgba(153, 102, 255, 0.2)",
                "borderColor": "rgba(153, 102, 255, 1)",
                "borderWidth": 1
            }]
        }

        engagementData = {
            "labels": post_labels,
            "datasets": [{
                "label": "Engagement Rate (%)",
                "data": engagement_rates,
                "backgroundColor": "rgba(255, 206, 86, 0.2)",
                "borderColor": "rgba(255, 206, 86, 1)",
                "borderWidth": 1
            }]
        }

        return render_template(
            "instagram_profile.html",
            profile={
                "full_name": full_name,
                "username": username,
                "bio": bio,
                "profile_pic": profile_pic,
                "verified": is_verified,
                "followers": followers,
                "following": following,
                "posts": len(media_data),
                "external_url": external_url
            },
            recent_posts=media_data,
            followersFollowingData=followersFollowingData,
            likesData=likesData,
            engagementData=engagementData
        )

    except Exception as e:
        return render_template("error.html", error_message=f"Instagram API error: {str(e)}")
    
@app.route('/save-profile/<platform>/<username>', methods=['POST'])
def save_profile(platform, username):
    if 'user_id' not in session:
        flash("You must log in to save profiles.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    print(f"[DEBUG] Saving for user_id: {user_id}, platform: {platform}, username: {username}")

    try:
        # Define the Firebase reference path
        ref_path = f'saved_profiles/{user_id}/{platform}'
        ref = db.reference(ref_path)
        print("[DEBUG] Firebase Reference Path:", ref_path)

        # Fetch existing data, or use empty list if none exists
        current_profiles = ref.get()
        if current_profiles is None:
            current_profiles = []

        # Prevent duplicates
        if username not in current_profiles:
            current_profiles.append(username)
            ref.set(current_profiles)
            print(f"[DEBUG] Username '{username}' saved for platform '{platform}'")
            flash("Profile saved successfully.")
        else:
            flash("This profile is already saved.")

    except Exception as e:
        print("[ERROR] Firebase save error:", str(e))
        flash("Failed to save profile. Please try again later.")

    return redirect(url_for(platform, username=username))

@app.route('/delete-profile/<platform>/<username>', methods=['POST'])
def delete_profile(platform, username):
    if 'user_id' not in session:
        flash("You must log in to delete profiles.")
        return redirect(url_for('login'))

    user_id = session['user_id']
    try:
        ref = db.reference(f"/saved_profiles/{user_id}/{platform}")
        current = ref.get()
        if current and username in current:
            current.remove(username)
            ref.set(current)
            flash(f"{username} removed from saved {platform} profiles.")
        else:
            flash("Profile not found or already deleted.")
    except Exception as e:
        flash("Failed to delete profile. Please try again later.")

    return redirect(url_for('dashboard'))

@app.route('/hashtag-trend', methods=['GET', 'POST'])
def hashtag_trend():
    # Default hashtag if no form is submitted
    if request.method == 'POST':
        # Get the hashtag from the form
        hashtag = request.form['hashtag']  
    else:
        hashtag = "#fyp" 

    try:
        # Initialize PyTrends
        pytrends = TrendReq(hl='en-US', tz=360)
        pytrends.build_payload([hashtag], cat=0, timeframe='today 12-m', geo='', gprop='')

        # Get interest over time data for the hashtag
        data = pytrends.interest_over_time()

        if data.empty:
            flash("No data found for the hashtag trends.")
            return render_template('hashtag_trend.html', hashtag=hashtag, hashtags_data={})

        # Handle missing or undefined values in the data
        data = data.fillna(0)  # Replace missing data with 0

        # Prepare data for the chart 
        hashtags_data = {
            'labels': data.index.strftime('%Y-%m-%d').tolist(),
            'datasets': [{
                'label': f'{hashtag} Trend',
                'data': data[hashtag].tolist(),
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            }]
        }

        return render_template('hashtag_trend.html', hashtag=hashtag, hashtags_data=hashtags_data)

    except Exception as e:
        print(f"Error: {e}")
        flash(f"Error fetching hashtag trends: {str(e)}")
        return render_template('error.html', error_message="Failed to fetch hashtag trends.")

if __name__ == '__main__':
    app.run(debug=True)