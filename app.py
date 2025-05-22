from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, send_file
import requests
import json
import warnings
import firebase_admin
import time
import os
from firebase_admin import credentials, auth, db
from pytrends.request import TrendReq
from weasyprint import HTML
import matplotlib
matplotlib.use('Agg') 
from matplotlib import pyplot as plt
from io import BytesIO
import base64

# Ignore certain warnings
warnings.filterwarnings("ignore", category=FutureWarning)

app = Flask(__name__)
app.secret_key = 'e33d2f3c993db5c91c04f16cd344b61e' 
app.config['SESSION_COOKIE_SECURE'] = True  
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

FIREBASE_API_KEY = "AIzaSyBvWfBvCtN3x99L-4g9GxKEo8ep6HhqGKI" 
cred = credentials.Certificate('firebase_credentials.json') 
firebase_admin.initialize_app(cred, {
    'databaseURL': os.environ.get("FIREBASE_DATABASE_URL")
})

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']  

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for('signup'))

        try:
            # Create Firebase user
            user = auth.create_user(email=email, password=password)

            # Sign in using Firebase REST API to get ID token
            sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
            payload = {"email": email, "password": password, "returnSecureToken": True}
            res = requests.post(sign_in_url, data=json.dumps(payload))
            id_token = res.json().get("idToken")

            # Send verification email
            verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
            verify_payload = {"requestType": "VERIFY_EMAIL", "idToken": id_token}
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
            sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }

            response = requests.post(sign_in_url, data=json.dumps(payload), headers={"Content-Type": "application/json"})

            if response.status_code == 200:
                result = response.json()
                session['user_id'] = result['localId']
                session['user_email'] = result['email']
                flash("Login successful.")
                return redirect(url_for('dashboard'))
            else:
                error_msg = response.json().get('error', {}).get('message', '')
                print(f"Login failed: {error_msg}")
                flash("Invalid email or password.")

        except Exception as e:
            print("Login error:", str(e))
            flash("An error occurred during login. Please try again.")

    return render_template('login.html')


# Logout Route
@app.route('/logout')
def logout():
    session.clear()  # Clear the session data
    return redirect(url_for('login'))

# Dashboard Route
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

        return render_template("dashboard.html", user_email=user.email, saved_profiles=saved_profiles)

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
        "X-RapidAPI-Key": os.environ.get("RAPIDAPI_KEY"),
        "X-RapidAPI-Host": os.environ.get("TIKTOK_API_HOST")
    }
    
    try:
        # Fetch TikTok profile info
        info_response = requests.get(info_url, headers=headers, params=querystring)
        info_response.raise_for_status()
        full_data = info_response.json()

        # Check if profile data is missing or invalid
        if "data" not in full_data or "user" not in full_data["data"]:
            flash("Profile data not found. Please check the username and try again.")
            return redirect(url_for('dashboard'))  # Redirect to dashboard to try again

        user_data = full_data["data"]["user"]
        stats_data = full_data["data"]["stats"]

        # Fetch posts
        posts_response = requests.get(posts_url, headers=headers, params=querystring)
        posts_response.raise_for_status()
        posts_data = posts_response.json().get("data", {}).get("videos", [])

        # Check if posts data is empty
        if not posts_data:
            flash("No posts available for this profile.")
            return redirect(url_for('dashboard'))  # Redirect to dashboard to try again

        # Find most liked post
        most_liked_post = None
        max_likes = -1
        for post in posts_data:
            if post.get("digg_count", 0) > max_likes:
                most_liked_post = post
                max_likes = post["digg_count"]

        # Prepare data for charts
        video_labels, likes_over_time, views_over_time, engagement_rate_over_time = [], [], [], []

        for i, post in enumerate(posts_data[:5]):
            video_labels.append(f"Video {i + 1}")
            likes = post.get("digg_count", 0)
            comments = post.get("comment_count", 0)
            shares = post.get("share_count", 0)
            views = post.get("play_count", 1)

            likes_over_time.append(likes)
            views_over_time.append(views)

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

        # Benchmark values
        benchmark_engagement = 3.6
        benchmark_likes = 980
        benchmark_growth = 2.1

        # User values (real data already calculated)
        user_engagement = round(sum(engagement_rate_over_time) / len(engagement_rate_over_time), 2) if engagement_rate_over_time else 0
        user_likes = round(sum(likes_over_time) / len(likes_over_time), 2) if likes_over_time else 0
        user_growth = 2.9  # Replace with dynamic value if stored historically

        # Normalise user values relative to benchmarks
        user_values = [
            user_engagement / benchmark_engagement if benchmark_engagement else 0,
            user_likes / benchmark_likes if benchmark_likes else 0,
            user_growth / benchmark_growth if benchmark_growth else 0
        ]

        benchmark_values = [1, 1, 1]  # Benchmark bars = 100% reference

        labels = ['Engagement Rate', 'Avg Likes', 'Monthly Growth']
        x = range(len(labels))
        width = 0.35

        # Plot
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar([p - width/2 for p in x], user_values, width, label='Your Profile', color='dodgerblue')
        ax.bar([p + width/2 for p in x], benchmark_values, width, label='Benchmark (100%)', color='lightgray')

        ax.set_ylabel('Normalised Score (1 = Benchmark)')
        ax.set_title('Performance Benchmarking (Relative to Benchmark)')
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=15)
        ax.set_ylim(0, max(max(user_values), 1.2))  # Extend y-limit slightly for clarity
        ax.legend()

  
        for i, v in enumerate(user_values):
            ax.text(x[i] - width/2, v + 0.05, f"{v:.2f}", ha='center', fontsize=8)
        for i, v in enumerate(benchmark_values):
            ax.text(x[i] + width/2, v + 0.05, f"{v:.2f}", ha='center', fontsize=8)

        plt.tight_layout()

        # Encode chart as base64 for embedding in HTML
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        benchmark_chart = base64.b64encode(buffer.read()).decode('utf-8')
        buffer.close()
        plt.close()



        return render_template(
            'tiktok_profile.html',
            user=user_data,
            stats=stats_data,
            posts=posts_data,
            most_liked=most_liked_post,
            likesData=likesData,
            viewsData=viewsData,
            engagementRateData=engagementRateData,
            followersFollowingData=followersFollowingData,
            benchmark_chart=benchmark_chart
        )

    except requests.exceptions.RequestException as e:
        flash("Failed to fetch TikTok data. Please try again later.")
        return redirect(url_for('dashboard'))  # Redirect to dashboard after error
    
@app.route('/tiktok/<username>/download-report', methods=['POST'])
def download_tiktok_report(username):
    if 'user_id' not in session:
        flash("You must log in to download reports.")
        return redirect(url_for('login'))

    info_url = "https://tiktok-scraper7.p.rapidapi.com/user/info"
    posts_url = "https://tiktok-scraper7.p.rapidapi.com/user/posts"
    querystring = {"unique_id": username}
    headers = {
        "X-RapidAPI-Key": os.environ.get("RAPIDAPI_KEY"),
        "X-RapidAPI-Host": os.environ.get("TIKTOK_API_HOST")
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
        "X-RapidAPI-Key": os.environ.get("RAPIDAPI_KEY"),
        "X-RapidAPI-Host": os.environ.get("IG_API_HOST")
    }

    try:
        # Step 1: Get profile info
        profile_response = requests.get(info_url, headers=headers, params={"username": username})
        profile_response.raise_for_status()
        response_json = profile_response.json()

        user_data = response_json.get("user")
        if not user_data:
            flash("No Instagram profile data found. Please check the username and try again.")
            return redirect(url_for('dashboard'))  # Redirect to dashboard

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
            flash("User ID not found in profile data.")
            return redirect(url_for('dashboard'))  # Redirect to dashboard

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
            flash("Instagram API returned unexpected data format.")
            return redirect(url_for('dashboard'))  # Redirect to dashboard

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
        flash(f"Instagram API error: {str(e)}")
        return redirect(url_for('dashboard'))  # Redirect to dashboard after error
    
@app.route('/save-profile/<platform>/<username>', methods=['POST'])
def save_profile(platform, username):
    if 'user_id' not in session:
        flash("You must log in to save profiles.")
        return redirect(url_for('login'))

    user_id = session['user_id']

    try:
        # Define the Firebase reference path
        ref_path = f'saved_profiles/{user_id}/{platform}'
        ref = db.reference(ref_path)

        # Fetch existing data, or use empty list if none exists
        current_profiles = ref.get()
        if current_profiles is None:
            current_profiles = []

        # Prevent duplicates
        if username not in current_profiles:
            current_profiles.append(username)
            ref.set(current_profiles)
            flash("Profile saved successfully.")
        else:
            flash("This profile is already saved.")

    except Exception as e:
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

@app.route('/instagram/<username>/download-report', methods=['POST'])
def download_instagram_report(username):

    if 'user_id' not in session:
        flash("You must log in to download reports.")
        return redirect(url_for('login'))

    info_url = "https://instagram-premium-api-2023.p.rapidapi.com/v1/user/web_profile_info"
    media_url = "https://instagram-premium-api-2023.p.rapidapi.com/v1/user/medias"

    headers = {
        "X-RapidAPI-Key": os.environ.get("RAPIDAPI_KEY"),
        "X-RapidAPI-Host": os.environ.get("IG_API_HOST")
    }

    try:
        # Step 1: Get profile info
        profile_response = requests.get(info_url, headers=headers, params={"username": username})
        profile_response.raise_for_status()
        response_json = profile_response.json()
        user_data = response_json.get("user")

        # Step 2: Get media data
        media_response = requests.get(media_url, headers=headers, params={"user_id": user_data["id"], "amount": 5})
        media_response.raise_for_status()
        media_data = media_response.json()

        # Step 3: Build top_posts table data
        top_posts = []
        for post in media_data[:5]:
            comment_count = post.get("comment_count", 0)
            like_count = post.get("like_count", 0)
            top_posts.append({"comments": comment_count, "likes": like_count})


        # Step 4: Render and generate PDF
        rendered = render_template(
            "instagram_report.html",
            profile=user_data,
            top_posts=top_posts  
        )
        pdf = HTML(string=rendered).write_pdf()

        print(f"PDF generated for {username}, content size: {len(pdf)} bytes")

        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=instagram_{username}_report.pdf'
        return response

    except Exception as e:
        flash(f"Could not generate report: {str(e)}", "danger")
        return redirect(url_for('instagram', username=username))
    
# Cache expiration time (in seconds)
CACHE_EXPIRATION_TIME = 600   # 10 minutes (for caching the hashtag results)
last_fetched_time = None  # Timestamp of the last API call
last_request_time = None  # Timestamp of the last user request

# Cache for storing hashtag data
hashtag_cache = {}

@app.route('/hashtag-trends', methods=['GET', 'POST'])
def hashtag_trends():
    global last_fetched_time, hashtag_cache, last_request_time

    if 'user_id' not in session:
        flash("You must log in to view hashtag trends.")
        return redirect(url_for('login'))

    graph_url = None
    hashtag = None

    # Get current time
    current_time = time.time()

    # 15-second cooldown between requests
    if last_request_time and current_time - last_request_time < 15:
        wait_time = 15 - (current_time - last_request_time)
        flash(f"Please wait {int(wait_time)} seconds before entering a new hashtag.")
        return redirect(request.url)  # Redirect to prevent a new request

    if request.method == 'POST':
        hashtag = request.form['hashtag'].strip('#')

        # Check if we have cached data and it's not expired
        if hashtag in hashtag_cache and current_time - last_fetched_time < CACHE_EXPIRATION_TIME:
            print(f"Using cached data for #{hashtag}")
            graph_url = hashtag_cache[hashtag]
        else:
            print(f"Fetching fresh data for #{hashtag}")
            # Fetch the trend data for the hashtag using PyTrends
            pytrends = TrendReq(hl='en-US', tz=360)
            pytrends.build_payload([hashtag], timeframe='now 7-d', geo='US')

            try:
                # Get interest over time for the hashtag
                interest_over_time_df = pytrends.interest_over_time()

                if not interest_over_time_df.empty:
                    # Plot the trend data
                    plt.figure(figsize=(10, 6))
                    plt.plot(interest_over_time_df.index, interest_over_time_df[hashtag], marker='o', color='b')
                    plt.title(f"Popularity of #{hashtag} Over the Last 7 Days")
                    plt.xlabel("Date")
                    plt.ylabel("Popularity (Interest Over Time)")
                    plt.grid(True)

                    # Save the plot to a BytesIO object
                    buffer = BytesIO()
                    plt.savefig(buffer, format='png')
                    buffer.seek(0)
                    graph_url = base64.b64encode(buffer.read()).decode('utf-8')  # Convert the image to base64 string
                    buffer.close()
                    plt.close()

                    # Cache the result for the hashtag
                    hashtag_cache[hashtag] = graph_url
                    last_fetched_time = current_time  # Update the cache time

            except Exception as e:
                flash(f"Error fetching data for #{hashtag}: {str(e)}")

        # Update the last request time to current time
        last_request_time = current_time

    return render_template('hashtag_trend.html', graph_url=graph_url, hashtag=hashtag)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)