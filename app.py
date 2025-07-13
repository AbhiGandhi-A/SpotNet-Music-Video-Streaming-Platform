import mysql
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, Response
import os
from flask_cors import CORS
from datetime import datetime
import os
from flask import send_from_directory, jsonify, session, redirect, url_for
import pymysql
from flask import session
from flask_socketio import SocketIO, emit, leave_room
import base64
from flask import send_from_directory, redirect, url_for, flash
import pymysql
from apscheduler.schedulers.background import BackgroundScheduler
import time
import urllib.parse
from mimetypes import guess_type
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

app = Flask(__name__)
app.secret_key = "spotnet"
app.config['SESSION_PERMANENT'] = False
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

EXTERNAL_HDD_PATH = 'G:\\Spotnet'


# Database connection
def get_db_connection():
    return pymysql.connect(
        host='127.0.0.1',
        user='root',
        password='Abhi@3014',
        database='spotnet',
        cursorclass=pymysql.cursors.DictCursor
    )


# Routes

@app.route('/movie/<int:movie_id>/play')
def play_movie(movie_id):
    import os
    from flask import send_file, jsonify, session
    from pymysql import connect

    user_id = session.get('user_id')  # Assuming user_id is stored in the session
    if not user_id or not has_active_subscription(user_id):
        return redirect(url_for('purchase_subscription'))  # Redirect if no active subscription.css

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Fetch movie information
            cursor.execute("SELECT title, file_path FROM movies WHERE id=%s", (movie_id,))
            movie = cursor.fetchone()

            if movie:
                file_path = movie['file_path']  # Full path stored in the database
                if os.path.exists(file_path):
                    # Insert or update user activity
                    username = session.get('user')
                    if username:
                        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                        user = cursor.fetchone()

                        if user:
                            user_id = user['id']
                            # Check if the activity already exists for this user and movie
                            cursor.execute("""SELECT * FROM user_activity WHERE user_id = %s AND movie_id = %s""", (user_id, movie_id))
                            existing_activity = cursor.fetchone()

                            if existing_activity:
                                cursor.execute("""
                                    UPDATE user_activity
                                    SET activity_type = 'play', timestamp = NOW()
                                    WHERE user_id = %s AND movie_id = %s
                                """, (user_id, movie_id))
                            else:
                                cursor.execute("""
                                    INSERT INTO user_activity (user_id, movie_id, activity_type, timestamp)
                                    VALUES (%s, %s, 'play', NOW())
                                """, (user_id, movie_id))

                            connection.commit()

                    return send_file(file_path, as_attachment=False, mimetype='video/mp4')
                else:
                    return jsonify({'error': f'Movie file not found at {file_path}'}), 404

            return jsonify({'error': 'Movie not found'}), 404
    except Exception as e:
        connection.rollback()  # Rollback in case of any errors
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()



@app.route('/song/<int:song_id>/play')
def play_song(song_id):
    user_id = session.get('user_id')  # Assuming user_id is stored in the session
    if not user_id or not has_active_subscription(user_id):
        return redirect(url_for('purchase_subscription'))  # Redirect if no active subscription.css

    connection = get_db_connection()
    cursor = connection.cursor()  # Use cursor explicitly here
    try:
        cursor.execute("SELECT title, file_path FROM songs WHERE id=%s", (song_id,))
        song = cursor.fetchone()

        if song and song['file_path']:
            # Construct the full file path
            file_path = os.path.join(EXTERNAL_HDD_PATH, song['file_path'])

            if os.path.exists(file_path):
                # Insert or update user activity
                username = session.get('user')
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()

                if user:
                    user_id = user['id']
                    # Check if the activity already exists for this user and song
                    cursor.execute("""
                        SELECT * FROM user_activity
                        WHERE user_id = %s AND song_id = %s
                    """, (user_id, song_id))
                    existing_activity = cursor.fetchone()

                    if existing_activity:
                        cursor.execute("""
                            UPDATE user_activity
                            SET activity_type = 'play', timestamp = NOW()
                            WHERE user_id = %s AND song_id = %s
                        """, (user_id, song_id))
                    else:
                        cursor.execute("""
                            INSERT INTO user_activity (user_id, song_id, activity_type, timestamp)
                            VALUES (%s, %s, 'play', NOW())
                        """, (user_id, song_id))

                    connection.commit()

                return send_from_directory(
                    os.path.dirname(file_path),
                    os.path.basename(file_path),
                    as_attachment=False
                )
            else:
                return jsonify({'error': 'Song file not found'}), 404

        return jsonify({'error': 'Song not found'}), 404

    finally:
        cursor.close()  # Ensure cursor is closed after the operations
        connection.close()  # Close connection


@app.route('/song/<int:song_id>/download')
def download_song(song_id):
    user_id = session.get('user_id')  # Assuming user_id is stored in the session
    if not user_id or not has_active_subscription(user_id):
        return redirect(url_for('purchase_subscription'))  # Redirect if no active subscription

    # Get user's download folder from the database
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT title, file_path, download_folder FROM songs WHERE id=%s", (song_id,))
            song = cursor.fetchone()

            cursor.execute("SELECT download_folder FROM users WHERE id=%s", (user_id,))
            user = cursor.fetchone()

        if song and song['file_path'] and user:
            # Get the user's download folder
            download_folder = user['download_folder']
            if not download_folder:
                return jsonify({'error': 'Download folder not set'}), 400  # User hasn't set a download folder

            # Construct the full file path
            file_path = os.path.join(EXTERNAL_HDD_PATH, song['file_path'])

            if os.path.exists(file_path):
                # Move or copy the song to the user's selected download folder
                filename = f"{song['title']}.mp3"
                destination_path = os.path.join(download_folder, filename)

                # Send the file to the user's download folder
                return send_from_directory(
                    os.path.dirname(file_path),
                    os.path.basename(file_path),
                    as_attachment=True,
                    download_name=filename
                )
            else:
                return jsonify({'error': 'Song file not found'}), 404

        return jsonify({'error': 'Song not found'}), 404

    except pymysql.MySQLError as e:
        print(f"Database error: {e}")
        return jsonify({'error': 'Database error occurred'}), 500

    finally:
        connection.close()



@app.route('/movie/<int:movie_id>/download')
def download_movie(movie_id):
    user_id = session.get('user_id')  # Assuming user_id is stored in the session
    if not user_id or not has_active_subscription(user_id):
        return redirect(url_for('purchase_subscription'))  # Redirect if no active subscription

    # Get user's download folder from the database
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT title, file_path, download_folder FROM movies WHERE id=%s", (movie_id,))
            movie = cursor.fetchone()

            cursor.execute("SELECT download_folder FROM users WHERE id=%s", (user_id,))
            user = cursor.fetchone()

        if movie and movie['file_path'] and user:
            # Get the user's download folder
            download_folder = user['download_folder']
            if not download_folder:
                return jsonify({'error': 'Download folder not set'}), 400  # User hasn't set a download folder

            # Construct the full file path
            file_path = os.path.join(EXTERNAL_HDD_PATH, movie['file_path'])

            if os.path.exists(file_path):
                # Move or copy the movie to the user's selected download folder
                filename = f"{movie['title']}.mp4"
                destination_path = os.path.join(download_folder, filename)

                # Send the file to the user's download folder
                return send_from_directory(
                    os.path.dirname(file_path),
                    os.path.basename(file_path),
                    as_attachment=True,
                    download_name=filename
                )
            else:
                return jsonify({'error': 'Movie file not found'}), 404

        return jsonify({'error': 'Movie not found'}), 404

    except pymysql.MySQLError as e:
        print(f"Database error: {e}")
        return jsonify({'error': 'Database error occurred'}), 500

    finally:
        connection.close()


@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Fetch movie details
            cursor.execute("""
                SELECT title, description, language, category, thumbnail, id
                FROM movies WHERE id=%s
            """, (movie_id,))
            movie = cursor.fetchone()

            # Fetch average rating and total number of ratings for the movie
            cursor.execute("""
                SELECT AVG(rating) AS average_rating, COUNT(rating) AS total_ratings
                FROM ratings
                WHERE movie_id = %s
            """, (movie_id,))
            rating_data = cursor.fetchone()
            average_rating = rating_data['average_rating'] if rating_data['average_rating'] is not None else 0
            total_ratings = rating_data['total_ratings'] if rating_data['total_ratings'] is not None else 0

            # Fetch comments for the movie
            cursor.execute("""
                SELECT comments.id AS comment_id, comments.comment, comments.timestamp, users.username
                FROM comments
                JOIN users ON comments.user_id = users.id
                WHERE comments.movie_id = %s
                ORDER BY comments.timestamp DESC
            """, (movie_id,))
            comments = cursor.fetchall()

            # Fetch songs associated with the movie
            cursor.execute("SELECT * FROM songs WHERE movie_id=%s", (movie_id,))
            songs = cursor.fetchall()

    except Exception as e:
        print(f"Error occurred while fetching movie details or comments: {e}")
        return jsonify({'error': 'An error occurred while fetching data.'}), 500
    finally:
        connection.close()

    # Convert movie thumbnail from binary data to base64 for display
    if movie and movie['thumbnail']:
        movie['thumbnail'] = base64.b64encode(movie['thumbnail']).decode('utf-8')

    return render_template('movie_details.html', movie=movie, average_rating=average_rating, total_ratings=total_ratings, comments=comments, songs=songs)


# Utility function to check active subscription.css
# Utility function to check active subscription.css
def has_active_subscription(user_id):
    # Check if user_id exists in session and if the subscription.css is still valid
    if 'user_id' in session:
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT end_date
                    FROM user_subscriptions
                    WHERE user_id = %s AND end_date >= CURDATE()
                    LIMIT 1
                """, (user_id,))
                subscription = cursor.fetchone()
                return subscription is not None
        finally:
            connection.close()
    return False


# Route to purchase a subscription.css
@app.route('/purchase_subscription', methods=['GET', 'POST'])
def purchase_subscription():
    connection = get_db_connection()
    if request.method == 'POST':
        subscription_id = request.form.get('subscription_id')
        username = session.get('user')  # Get the username from session

        try:
            # Fetch the user_id and email from the database based on the username
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, email FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()

            if user:
                user_id = user['id']  # Get the user_id
                user_email = user['email']  # Get the user's email

                # Fetch subscription.css details
                with connection.cursor() as cursor:
                    cursor.execute("SELECT duration_days, price, name FROM subscriptions WHERE id = %s", (subscription_id,))
                    subscription = cursor.fetchone()

                if subscription:
                    # Add subscription.css to user
                    start_date = datetime.now().date()
                    end_date = start_date + timedelta(days=subscription['duration_days'])

                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO user_subscriptions (user_id, subscription_id, start_date, end_date)
                            VALUES (%s, %s, %s, %s)
                        """, (user_id, subscription_id, start_date, end_date))
                        connection.commit()

                    # Set user session to have active subscription.css
                    session['user_id'] = user_id  # Store the user_id in session
                    session['subscription_end_date'] = end_date  # Store subscription.css end date in session

                    # Send email with subscription.css details
                    send_subscription_email(user_email, subscription)

                    flash("Subscription purchased successfully!", "success")
                    return redirect(url_for('home'))
                else:
                    flash("Invalid subscription.css selected.", "error")
            else:
                flash("User not found.", "error")

        except Exception as e:
            print(f"Error during insert: {e}")
            connection.rollback()  # Rollback the transaction if there was an error
            flash("An error occurred while processing your subscription.css.", "error")
            return redirect(url_for('purchase_subscription'))  # Avoid showing the success flash again
        finally:
            connection.close()

    # Fetch all subscriptions
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM subscriptions")
        subscriptions = cursor.fetchall()

    return render_template('purchase_subscription.html', subscriptions=subscriptions)

@app.route('/subscription_page/<username>')
def subscription_page(username):
    connection = get_db_connection()

    # Fetch the user's current subscription
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT s.name, s.price, us.start_date, us.end_date
            FROM user_subscriptions us
            JOIN subscriptions s ON us.subscription_id = s.id
            WHERE us.user_id = (SELECT id FROM users WHERE username = %s) 
            AND us.end_date >= CURDATE()
            ORDER BY us.start_date DESC
            LIMIT 1
        """, (username,))
        current_subscription = cursor.fetchone()

        # Fetch the user's past subscriptions
        cursor.execute("""
            SELECT s.name, s.price, us.start_date, us.end_date
            FROM user_subscriptions us
            JOIN subscriptions s ON us.subscription_id = s.id
            WHERE us.user_id = (SELECT id FROM users WHERE username = %s) 
            AND us.end_date < CURDATE()
            ORDER BY us.end_date DESC
        """, (username,))
        past_subscriptions = cursor.fetchall()

        # Fetch all available subscriptions
        cursor.execute("SELECT * FROM subscriptions")
        subscriptions = cursor.fetchall()

    connection.close()

    return render_template('subscription_page.html',
                           username=username,
                           current_subscription=current_subscription,
                           past_subscriptions=past_subscriptions,
                           subscriptions=subscriptions)


# Function to send subscription.css email
def send_subscription_email(user_email, subscription):
    sender_email = "spotnet432@gmail.com"
    sender_password = "remb cmks dxlc homi"

    message = MIMEMultipart("alternative")
    message["Subject"] = f"Subscription Confirmation - SpotNet"
    message["From"] = sender_email
    message["To"] = user_email

    html = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; line-height: 1.5; padding: 20px; background-color: #f4f4f4; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #2b5f97;">SpotNet Subscription Confirmation</h2>
            <p>Thank you for purchasing the <strong>{subscription['name']}</strong> plan!</p>
            <p><strong>Details:</strong></p>
            <ul>
                <li>Price: ${subscription['price']}</li>
                <li>Duration: {subscription['duration_days']} days</li>
            </ul>
            <p>If you have any questions, feel free to contact us at support@spotnet.com.</p>
            <div style="text-align: center; margin-top: 20px;">
                <img src="https://your-logo-url.com/logo.png" alt="SpotNet Logo" style="max-width: 150px;">
            </div>
        </div>
    </body>
    </html>
    """

    # Attach HTML content
    message.attach(MIMEText(html, "html"))

    # Send the email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, user_email, message.as_string())


@app.route('/movie/<int:movie_id>/add_rating', methods=['POST'])
def add_rating(movie_id):
    if 'user' not in session:
        return redirect(url_for('login'))  # Redirect to login if the user is not logged in

    username = session['user']  # Get the username from the session

    # Fetch the user_id from the database using the username
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

    if not user:
        return "User not found", 404  # Handle the case where the user is not found

    rating = request.form.get('rating')  # Get the rating value from the form

    if not rating:
        return jsonify({'error': 'No rating selected'}), 400

    user_id = user['id']  # Get the user_id from the query result

    # Check if the user has already rated this movie
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id FROM ratings WHERE movie_id = %s AND user_id = %s
        """, (movie_id, user_id))
        existing_rating = cursor.fetchone()

        if existing_rating:
            # Update existing rating if it exists
            cursor.execute("""
                UPDATE ratings SET rating = %s WHERE movie_id = %s AND user_id = %s
            """, (rating, movie_id, user_id))
        else:
            # Insert a new rating if the user hasn't rated yet
            cursor.execute("""
                INSERT INTO ratings (movie_id, user_id, rating)
                VALUES (%s, %s, %s)
            """, (movie_id, user_id, rating))

        # Update user activity as well
        cursor.execute("""
            INSERT INTO user_activity (user_id, movie_id, activity_type, timestamp)
            VALUES (%s, %s, 'rate', NOW())
        """, (user_id, movie_id))

        connection.commit()

    connection.close()

    return redirect(url_for('movie_details', movie_id=movie_id))


@app.route('/movie/<int:movie_id>/add_comment', methods=['POST'])
def add_comment(movie_id):
    if 'user' not in session:
        return redirect(url_for('login'))  # Redirect to login if the user is not logged in

    username = session['user']  # Get the username from the session

    # Fetch the user_id from the database using the username
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

    if not user:
        return "User not found", 404  # Handle the case where the user is not found

    user_id = user['id']  # Get the user_id from the query result
    comment = request.form['comment']  # Get the comment from the form

    # Insert the comment into the comments table
    with connection.cursor() as cursor:
        cursor.execute(""" 
            INSERT INTO comments (movie_id, user_id, comment)
            VALUES (%s, %s, %s)
        """, (movie_id, user_id, comment))
        connection.commit()

    # Track the user activity for adding a comment
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO user_activity (user_id, movie_id, activity_type, timestamp)
            VALUES (%s, %s, 'comment', NOW())
        """, (user_id, movie_id))
        connection.commit()

    connection.close()

    return redirect(url_for('movie_details', movie_id=movie_id))

@app.route('/view_movie/<int:movie_id>')
def view_movie(movie_id):
    # Fetch the movie details from the database using the movie_id
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT m.*, r.name AS region_name
                FROM movies m
                LEFT JOIN regions r ON m.region_id = r.id
                WHERE m.id = %s
            """, (movie_id,))
            movie = cursor.fetchone()

        # If movie is found, convert the thumbnail to base64 and render the movie details page
        if movie:
            # Convert the thumbnail to base64 if it's stored as binary data
            if movie['thumbnail']:
                movie['thumbnail'] = base64.b64encode(movie['thumbnail']).decode('utf-8')

            # Fetch the user details (if logged in)
            user = None
            if 'user_id' in session:
                # Re-open a new connection to fetch user details to avoid closing the initial one
                with get_db_connection().cursor() as cursor:
                    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
                    user = cursor.fetchone()

            return render_template('view_movie.html', movie=movie, user=user)
        else:
            flash("Movie not found!")
            return redirect(url_for('movies_page'))
    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({'error': 'An error occurred while fetching movie details.'}), 500
    finally:
        connection.close()

@app.route('/song/<int:song_id>', methods=['GET'])
def view_song(song_id):
    try:
        connection = get_db_connection()

        # Fetch the song details and associated movie information
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT songs.*, movies.title AS movie_title 
                FROM songs 
                JOIN movies ON songs.movie_id = movies.id
                WHERE songs.id = %s
            """, (song_id,))
            song = cursor.fetchone()

        if song is None:
            return "Song not found", 404

        # Fetch movie poster (thumbnail)
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT thumbnail FROM movies WHERE id = %s", (song['movie_id'],))
            movie_thumbnail = cursor.fetchone()

        # Handle thumbnail (poster) encoding
        if movie_thumbnail and movie_thumbnail['thumbnail']:
            movie_poster = base64.b64encode(movie_thumbnail['thumbnail']).decode('utf-8')
        else:
            movie_poster = None

        # Define the external drive path to the song file
        song_file_path = os.path.join("G:\\Movies", song['file_path'])

        return render_template('view_song.html', song=song, movie_poster=movie_poster, song_file_path=song_file_path)

    except pymysql.MySQLError as e:
        # Handle any database errors
        print(f"Database error: {e}")
        return "Database error occurred", 500
    finally:
        if connection:
            connection.close()


@app.route('/admin/add_movie', methods=['GET', 'POST'])
def add_movie():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        # Fetch categories and regions
        cursor.execute("SELECT id, name FROM categories")
        categories = cursor.fetchall()

        cursor.execute("SELECT id, name FROM regions")
        regions = cursor.fetchall()

    if request.method == 'POST':
        # Get form data
        title = request.form['title']
        description = request.form['description']
        visibility = request.form['visibility']
        category_id = request.form['category']  # Selected category ID
        region_id = request.form['region']  # Selected region ID
        language = request.form['language']
        release_date = request.form['release_date']
        movie_file_path = request.form['movie_file_path']
        thumbnail_file = request.files['thumbnail_file']
        thumbnail_data = thumbnail_file.read()

        # Verify if the category exists
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM categories WHERE id = %s", (category_id,))
            category_row = cursor.fetchone()  # This will be None if no matching row is found

            if not category_row:  # If the query returned None
                flash("Invalid category ID.")
                return redirect(url_for('add_movie'))

            category_name = category_row['name']

            # Handle new region addition
        new_region = request.form.get('new_region')
        if new_region:
            with connection.cursor() as cursor:
                # Check if the region already exists
                cursor.execute("SELECT id FROM regions WHERE name = %s", (new_region,))
                existing_region = cursor.fetchone()

                if not existing_region:
                    cursor.execute("INSERT INTO regions (name) VALUES (%s)", (new_region,))
                    connection.commit()
                    # Retrieve the new region ID
                    cursor.execute("SELECT id FROM regions WHERE name = %s", (new_region,))
                    region_id = cursor.fetchone()[0]  # Fetch new region ID
                else:
                    region_id = existing_region[0]  # Use the existing region ID

        # Insert movie data into the database
        with connection.cursor() as cursor:
            query = """
                INSERT INTO movies (title, description, thumbnail, file_path, visibility, category, region_id, language, release_date) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
                title, description, thumbnail_data, movie_file_path, visibility, category_name, region_id, language,
                release_date))
            connection.commit()

        connection.close()

        flash("Movie added successfully!")
        return redirect(url_for('dashboard'))

    return render_template('add_movie.html', categories=categories, regions=regions)


@app.route('/admin/add_song', methods=['GET', 'POST'])
def add_song():
    connection = get_db_connection()

    if request.method == 'POST':
        title = request.form['title']
        name = request.form['song_name']
        movie_id = request.form['movie_id']
        category = request.form['category']
        new_category = request.form.get('new_category')  # Get the new category input
        song_file_path = request.form['song_file_path']
        language = request.form['language']
        release_date = request.form['release_date']

        # If a new category is provided, insert it into the database
        if new_category:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM categories WHERE Category_song = %s", (new_category,))
                existing_category = cursor.fetchone()

                if not existing_category:
                    cursor.execute("INSERT INTO categories (Category_song) VALUES (%s)", (new_category,))
                    connection.commit()
                    flash("New category added successfully!", "success")
                    category = new_category  # Set the newly added category as the selected one
                else:
                    flash("Category already exists.", "warning")
                    category = existing_category['Category_song']  # Use the existing category name if already present
        else:
            # If no new category, use the selected category
            with connection.cursor() as cursor:
                cursor.execute("SELECT Category_song FROM categories WHERE id = %s", (category,))
                existing_category = cursor.fetchone()
                if existing_category:
                    category = existing_category['Category_song']  # Get the category name from the categories table
                else:
                    flash("Selected category doesn't exist.", "warning")
                    return redirect(url_for('add_song'))

        # Insert the song into the database with the category name (not the ID)
        with connection.cursor() as cursor:
            query = """
                INSERT INTO songs (title, song_name, movie_id, category, file_path, language, release_date) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (title, name, movie_id, category, song_file_path, language, release_date))
            connection.commit()

        flash("Song added successfully!", "success")
        return redirect(url_for('dashboard'))

    # Fetch movies and categories for dropdown lists
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, title FROM movies")
        movies = cursor.fetchall()

        cursor.execute("SELECT id, Category_song FROM categories")  # Fetch category name properly
        categories = cursor.fetchall()

    connection.close()

    return render_template('add_song.html', movies=movies, categories=categories)

@app.route('/add_category', methods=['POST'])
def add_category():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'success': False, 'message': 'Category name is required.'}), 400

    category_name = data['name']
    adult = data.get('adult', 0)

    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT Category_song FROM categories WHERE Category_song = %s", (category_name,))
            existing_category = cursor.fetchone()

            if existing_category:
                return jsonify({'success': False, 'message': 'Category already exists.'}), 400

            # Determine the name based on the adult flag
            name = "Normal" if adult == 0 else "Adult"

            cursor.execute("INSERT INTO categories (Category_song, adult, name) VALUES (%s, %s, %s)", (category_name, adult, name))
            connection.commit()
            return jsonify({'success': True, 'message': 'Category added successfully.'}), 201

    except pymysql.Error as err:
        print(f"Error: {err}")
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500

    finally:
        if connection and connection.open:
            connection.close()



@app.route('/get_playlists', methods=['GET'])
def get_playlists():
    username = request.args.get('username')
    if not username:
        return jsonify({"error": "User not found"}), 404

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name FROM playlists WHERE user_id = (SELECT id FROM users WHERE username = %s)", (username,))
            playlists = cursor.fetchall()
            return jsonify(playlists)
    except Exception as e:
        print(f"Error fetching playlists: {e}")
        return jsonify({"error": "Unable to fetch playlists"}), 500
    finally:
        connection.close()


@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    username = request.json.get('username')
    playlist_name = request.json.get('playlist_name')

    if not username or not playlist_name:
        return jsonify({"error": "Invalid input"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if not user:
                return jsonify({"error": "User not found"}), 404

            user_id = user['id']
            cursor.execute("INSERT INTO playlists (name, user_id) VALUES (%s, %s)", (playlist_name, user_id))
            connection.commit()
            return jsonify({"message": "Playlist created successfully"})
    except Exception as e:
        print(f"Error creating playlist: {e}")
        return jsonify({"error": "Unable to create playlist"}), 500
    finally:
        connection.close()


@app.route('/playlist/<int:playlist_id>', methods=['GET'])
def get_playlist_details(playlist_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name FROM playlists WHERE id = %s", (playlist_id,))
            playlist = cursor.fetchone()

            if not playlist:
                return jsonify({"error": "Playlist not found"}), 404

            cursor.execute("""
                SELECT pi.id, m.title AS movie_title, s.title AS song_title, m.id AS movie_id, s.id AS song_id
                FROM playlist_items pi 
                LEFT JOIN movies m ON pi.movie_id = m.id 
                LEFT JOIN songs s ON pi.song_id = s.id 
                WHERE pi.playlist_id = %s
            """, (playlist_id,))
            items = cursor.fetchall()

            # Fetch all movies for the add to playlist functionality
            cursor.execute("SELECT id, title FROM movies")
            movies = cursor.fetchall()

            # Fetch thumbnails separately and add to movie dictionaries
            for movie in movies:
                cursor.execute("SELECT thumbnail FROM movies WHERE id = %s", (movie['id'],))
                thumbnail_data = cursor.fetchone()
                if thumbnail_data and thumbnail_data['thumbnail']:
                    movie['thumbnail'] = base64.b64encode(thumbnail_data['thumbnail']).decode('utf-8')
                else:
                    movie['thumbnail'] = ""

            # Fetch all songs for the add to playlist functionality
            cursor.execute("SELECT id, title, movie_id FROM songs")
            songs = cursor.fetchall()

            # Fetch thumbnails separately and add to song dictionaries
            for song in songs:
                cursor.execute("""
                    SELECT m.thumbnail FROM movies m
                    JOIN songs s ON s.movie_id = m.id
                    WHERE s.id = %s
                """, (song['id'],))
                thumbnail_data = cursor.fetchone()

                if thumbnail_data and thumbnail_data['thumbnail']:
                    song['thumbnail'] = base64.b64encode(thumbnail_data['thumbnail']).decode('utf-8')
                else:
                    song['thumbnail'] = ""

            return render_template('playlist_details.html', playlist=playlist, items=items, movies=movies, songs=songs)
    except Exception as e:
        print(f"Error fetching playlist details: {e}")
        return jsonify({"error": "Unable to fetch playlist details"}), 500
    finally:
        connection.close()


@app.route('/playlist/<int:playlist_id>/delete', methods=['POST'])
def delete_playlist(playlist_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM playlist_items WHERE playlist_id = %s", (playlist_id,))
            cursor.execute("DELETE FROM playlists WHERE id = %s", (playlist_id,))
            connection.commit()
            return jsonify({"message": "Playlist deleted successfully"})
    except Exception as e:
        print(f"Error deleting playlist: {e}")
        return jsonify({"error": "Unable to delete playlist"}), 500
    finally:
        connection.close()


@app.route('/playlist/<int:playlist_id>/remove_item', methods=['POST'])
def remove_item_from_playlist(playlist_id):
    data = request.json
    actual_id = data.get('actual_id')  # Correct ID from frontend
    item_type = data.get('item_type')

    print(f"DEBUG: Received actual_id={actual_id}, item_type={item_type}, playlist_id={playlist_id}")

    if not actual_id or not item_type:
        return jsonify({"error": "Invalid input"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if item_type == "movie":
                query = "DELETE FROM playlist_items WHERE playlist_id = %s AND movie_id = %s"
            elif item_type == "song":
                query = "DELETE FROM playlist_items WHERE playlist_id = %s AND song_id = %s"
            else:
                return jsonify({"error": "Invalid item type"}), 400

            print(f"DEBUG: Executing query: {query} with params ({playlist_id}, {actual_id})")

            cursor.execute(query, (playlist_id, actual_id))
            connection.commit()

            if cursor.rowcount > 0:
                return jsonify({"message": "Item removed from playlist successfully"})
            else:
                return jsonify({"message": "No such item found in playlist"}), 404

    except Exception as e:
        print(f"Error removing item from playlist: {e}")
        return jsonify({"error": "Unable to remove item from playlist"}), 500
    finally:
        connection.close()


@app.route('/playlists/<username>')
def playlists_page(username):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Fetch user and playlists (your existing code)
            cursor.execute("SELECT id, name, profile_image FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()

            if not user:
                return jsonify({"error": "User not found"}), 404

            cursor.execute("SELECT id, name FROM playlists WHERE user_id = %s", (user['id'],))
            playlists = cursor.fetchall()



            # Fetch movies (Do NOT select thumbnail here)
            cursor.execute("SELECT id, title FROM movies")  # Select only id and title
            movies = cursor.fetchall()

            # Fetch thumbnails separately and add to movie dictionaries
            for movie in movies:
                cursor.execute("SELECT thumbnail FROM movies WHERE id = %s", (movie['id'],))
                thumbnail_data = cursor.fetchone()
                if thumbnail_data and thumbnail_data['thumbnail']:  # Check for None
                    movie['thumbnail'] = base64.b64encode(thumbnail_data['thumbnail']).decode('utf-8')
                else:
                    movie['thumbnail'] = ""  # Or a placeholder image URL

            # Fetch songs (Do NOT select thumbnail here)
            # Fetch songs (Do NOT select thumbnail here)
            cursor.execute("SELECT id, title, movie_id FROM songs")  # Select only id, title, and movie_id
            songs = cursor.fetchall()

            # Fetch thumbnails separately and add to song dictionaries
            for song in songs:
                cursor.execute("""
                    SELECT m.thumbnail FROM movies m
                    JOIN songs s ON s.movie_id = m.id
                    WHERE s.id = %s
                """, (song['id'],))
                thumbnail_data = cursor.fetchone()

                if thumbnail_data and thumbnail_data['thumbnail']:  # Check for None
                    song['thumbnail'] = base64.b64encode(thumbnail_data['thumbnail']).decode('utf-8')
                else:
                    song['thumbnail'] = ""  # Or a placeholder image URL
            # Or a placeholder image URL

            return render_template('playlists.html', user=user, playlists=playlists, movies=movies, songs=songs)

    except Exception as e:
        print(f"Error fetching playlists: {e}")  # VERY IMPORTANT for debugging
        return jsonify({"error": "Unable to fetch playlists"}), 500
    finally:
        connection.close()



@app.route('/move_movies', methods=['POST'])
def move_movies():
    playlist_id = request.json.get('playlist_id')
    new_playlist_name = request.json.get('new_playlist_name')

    if not playlist_id or not new_playlist_name:
        return jsonify({"error": "Invalid input"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if the new playlist already exists
            cursor.execute("SELECT id FROM playlists WHERE name = %s AND user_id = (SELECT user_id FROM playlists WHERE id = %s)",
                           (new_playlist_name, playlist_id))
            existing_playlist = cursor.fetchone()

            if not existing_playlist:
                # Create the new playlist
                cursor.execute("INSERT INTO playlists (name, user_id) SELECT %s, user_id FROM playlists WHERE id = %s",
                               (new_playlist_name, playlist_id))
                connection.commit()
                cursor.execute("SELECT id FROM playlists WHERE name = %s AND user_id = (SELECT user_id FROM playlists WHERE id = %s)",
                               (new_playlist_name, playlist_id))
                new_playlist_id = cursor.fetchone()['id']

                # Move the movies to the new playlist
                cursor.execute("""
                    INSERT INTO playlist_items (playlist_id, movie_id) 
                    SELECT %s, movie_id FROM playlist_items WHERE playlist_id = %s AND movie_id IS NOT NULL
                """, (new_playlist_id, playlist_id))

                # Optionally remove the movies from the original playlist
                cursor.execute("DELETE FROM playlist_items WHERE playlist_id = %s AND movie_id IS NOT NULL", (playlist_id,))
                connection.commit()

                return jsonify({"message": f"Movies moved to the new playlist: {new_playlist_name}"})
            else:
                return jsonify({"error": "Playlist with that name already exists."}), 400
    except Exception as e:
        print(f"Error moving movies: {e}")
        return jsonify({"error": "Unable to move movies"}), 500
    finally:
        connection.close()


@app.route('/add_to_playlist', methods=['POST'])
def add_to_playlist():
    username = request.json.get('username')
    playlist_id = request.json.get('playlist_id')
    item_id = request.json.get('item_id')  # Movie or song ID
    item_type = request.json.get('item_type')  # "movie" or "song"

    if not username or not playlist_id or not item_id or not item_type:
        return jsonify({"error": "Invalid input"}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if item_type == "movie":
                cursor.execute("INSERT INTO playlist_items (playlist_id, movie_id) VALUES (%s, %s)", (playlist_id, item_id))
            elif item_type == "song":
                cursor.execute("INSERT INTO playlist_items (playlist_id, song_id) VALUES (%s, %s)", (playlist_id, item_id))
            connection.commit()
            return jsonify({"message": "Item added to playlist successfully"})
    except Exception as e:
        print(f"Error adding item to playlist: {e}")
        return jsonify({"error": "Unable to add item to playlist"}), 500
    finally:
        connection.close()

@app.route('/movie/<int:movie_id>/add_to_playlist', methods=['POST'])
def add_movie_to_playlist(movie_id):
    username = request.json.get('username')
    playlist_id = request.json.get('playlist_id')

    if not username or not playlist_id:
        return jsonify({"error": "Invalid input. Please provide username and playlist_id."}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if the movie exists
            cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
            movie = cursor.fetchone()
            if not movie:
                return jsonify({"error": "Movie not found."}), 404

            # Add the movie to the playlist
            cursor.execute("INSERT INTO playlist_items (playlist_id, movie_id) VALUES (%s, %s)", (playlist_id, movie_id))
            connection.commit()
            return jsonify({"message": "Movie added to playlist successfully"})
    except Exception as e:
        print(f"Error adding movie to playlist: {e}")
        return jsonify({"error": "Unable to add movie to playlist due to server error."}), 500
    finally:
        connection.close()

@app.route('/song/<int:song_id>/add_to_playlist', methods=['POST'])
def add_song_to_playlist(song_id):
    username = request.json.get('username')
    playlist_id = request.json.get('playlist_id')

    if not username or not playlist_id:
        return jsonify({"error": "Invalid input. Please provide username and playlist_id."}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if the song exists
            cursor.execute("SELECT * FROM songs WHERE id = %s", (song_id,))
            song = cursor.fetchone()
            if not song:
                return jsonify({"error": "Song not found."}), 404

            # Add the song to the playlist
            cursor.execute("INSERT INTO playlist_items (playlist_id, song_id) VALUES (%s, %s)", (playlist_id, song_id))
            connection.commit()
            return jsonify({"message": "Song added to playlist successfully"})
    except Exception as e:
        print(f"Error adding song to playlist: {e}")
        return jsonify({"error": "Unable to add song to playlist due to server error."}), 500
    finally:
        connection.close()

@app.route('/movies_page')
def movies_page():
    region = request.args.get('region', 'all')  # Default to 'all' if no region is selected
    language = request.args.get('language', '')
    release_date = request.args.get('release_date', '')

    connection = get_db_connection()
    cursor = connection.cursor()

    # Fetch all regions for the filter dropdown
    cursor.execute("SELECT id, name FROM regions")
    regions = cursor.fetchall()

    # Fetch distinct languages for the filter dropdown
    cursor.execute("SELECT DISTINCT language FROM movies")
    languages = cursor.fetchall()

    # Build the query to fetch movies
    query = "SELECT id, title, thumbnail, category, language, release_date, region_id FROM movies WHERE 1=1"
    params = []

    if region != 'all':
        query += " AND region_id = %s"
        params.append(region)

    if language:
        query += " AND language = %s"
        params.append(language)

    if release_date:
        query += " AND release_date = %s"
        params.append(release_date)

    cursor.execute(query, tuple(params))
    movies = cursor.fetchall()

    connection.close()

    # Process the thumbnails
    for movie in movies:
        if movie['thumbnail']:
            movie['thumbnail'] = base64.b64encode(movie['thumbnail']).decode('utf-8')

    return render_template(
        'movies_page.html',
        movies=movies,
        regions=regions,
        languages=languages
    )



@app.route('/songs_page')
def songs_page():
    category = request.args.get('category', 'normal')
    language = request.args.get('language', '')
    release_date = request.args.get('release_date', '')

    connection = get_db_connection()

    # Fetch categories from the database
    with connection.cursor() as cursor:
        cursor.execute("SELECT Category_song FROM categories")
        categories = cursor.fetchall()

    # Query songs with filters
    query = "SELECT id, title, category, language, release_date, movie_id FROM songs WHERE 1=1"
    params = []

    if category != 'normal':
        query += " AND category = %s"
        params.append(category)

    if language:
        query += " AND language = %s"
        params.append(language)

    if release_date:
        query += " AND release_date = %s"
        params.append(release_date)

    with connection.cursor() as cursor:
        cursor.execute(query, tuple(params))
        songs = cursor.fetchall()

    # Base64 encode the thumbnails for each song
    for song in songs:
        # Fetch the movie's thumbnail
        with connection.cursor() as cursor:
            cursor.execute("SELECT thumbnail FROM movies WHERE id = %s", (song['movie_id'],))
            movie_thumbnail = cursor.fetchone()
            if movie_thumbnail and movie_thumbnail['thumbnail']:
                song['thumbnail'] = base64.b64encode(movie_thumbnail['thumbnail']).decode('utf-8')
            else:
                song['thumbnail'] = None

    connection.close()

    return render_template('songs_page.html', songs=songs, categories=categories)

@app.route('/add_thumbnail', methods=['GET', 'POST'])
def add_thumbnail():
    if request.method == 'POST':
        movie_id = request.form['movie_id']
        thumbnail_file = request.files['thumbnail_file']
        thumbnail_data = thumbnail_file.read()

        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = "UPDATE movies SET thumbnail=%s WHERE id=%s"
            cursor.execute(query, (thumbnail_data, movie_id))
            connection.commit()
        connection.close()

        flash("Thumbnail added successfully!")
        return redirect(url_for('dashboard'))

    return render_template('add_thumbnail.html')


@app.route('/chat')
def chat():
    if 'user_id' not in session or 'username' not in session:
        flash("You need to log in first!", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']
    username = session['username']

    return render_template('chat.html', user_id=user_id, username=username)

@app.route('/search_users', methods=['GET'])
def search_users():
    search_query = request.args.get('query', '').strip()
    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    if search_query:
        sql = """
            SELECT u.id, u.name, u.username, 
                   (SELECT status FROM friend_requests 
                    WHERE sender_id = %s AND receiver_id = u.id) as request_status,
                   (SELECT status FROM friend_requests
                    WHERE receiver_id = %s AND sender_id = u.id) as received_request_status,
                    (SELECT 1 FROM friends WHERE user_id = %s and friend_id = u.id) as is_friend
            FROM users u
            WHERE (u.username LIKE %s OR u.name LIKE %s) AND u.id != %s
        """
        search_term = f"%{search_query}%"
        cursor.execute(sql, (user_id, user_id, user_id, search_term, search_term, user_id))
    else:
        sql = """
            SELECT u.id, u.name, u.username,
                   (SELECT status FROM friend_requests 
                    WHERE sender_id = %s AND receiver_id = u.id) as request_status,
                    (SELECT status FROM friend_requests
                    WHERE receiver_id = %s AND sender_id = u.id) as received_request_status,
                    (SELECT 1 FROM friends WHERE user_id = %s and friend_id = u.id) as is_friend
            FROM users u
            WHERE u.id != %s
        """
        cursor.execute(sql, (user_id, user_id, user_id, user_id))

    users = cursor.fetchall()
    conn.close()

    user_list = []
    for user in users:
        user_data = {
            'id': user['id'],  # Access by dictionary key
            'name': user['name'],  # Access by dictionary key
            'username': user['username'],  # Access by dictionary key
            'request_status': user.get('request_status'),  # Use .get() to handle None
            'received_request_status': user.get('received_request_status'),
            'is_friend': user.get('is_friend')
        }
        user_list.append(user_data)

    return jsonify(user_list)

@app.route('/send_friend_request', methods=['POST'])
def send_friend_request():
    sender_id = session.get('user_id')
    data = request.get_json()
    receiver_id = data.get('receiver_id')

    if not receiver_id:
        return jsonify({"error": "Missing receiver_id"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM friend_requests WHERE sender_id = %s AND receiver_id = %s", (sender_id, receiver_id))
    existing_request = cursor.fetchone()

    if existing_request:
        return jsonify({"message": "Request already sent"}), 400

    cursor.execute("INSERT INTO friend_requests (sender_id, receiver_id) VALUES (%s, %s)", (sender_id, receiver_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Friend request sent successfully"}), 200

@app.route('/accept_friend_request', methods=['POST'])
def accept_friend_request():
    receiver_id = session.get('user_id')
    data = request.get_json()
    sender_id = data.get('request_id')

    if not sender_id:
        return jsonify({"error": "Missing request_id"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM friend_requests WHERE sender_id = %s AND receiver_id = %s AND status = 'pending'",
                   (sender_id, receiver_id))
    request_exists = cursor.fetchone()

    if not request_exists:
        return jsonify({"error": "Friend request not found or already accepted"}), 400

    cursor.execute("UPDATE friend_requests SET status = 'accepted' WHERE sender_id = %s AND receiver_id = %s",
                   (sender_id, receiver_id))

    cursor.execute("INSERT INTO friends (user_id, friend_id) VALUES (%s, %s), (%s, %s)",
                   (sender_id, receiver_id, receiver_id, sender_id))

    conn.commit()
    conn.close()

    return jsonify({"message": "Friend request accepted successfully"}), 200

@app.route('/friend_requests')
def get_friend_requests():
    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fr.id, fr.sender_id, u.name, u.username
        FROM friend_requests fr
        JOIN users u ON fr.sender_id = u.id
        WHERE fr.receiver_id = %s AND fr.status = 'pending'
    """, (user_id,))

    requests = cursor.fetchall()
    conn.close()

    return jsonify(requests)

@app.route('/friend_list', methods=['GET'])
def friend_list():
    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT u.id, u.name, u.username 
        FROM friends f 
        JOIN users u ON f.friend_id = u.id 
        WHERE f.user_id = %s
    """, (user_id,))

    friends = cursor.fetchall()
    conn.close()

    return jsonify(friends)

@app.route('/retrieve_movies', methods=['GET'])
def retrieve_movies():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, thumbnail FROM movies")
    movies = cursor.fetchall()

    movies_list = []
    for movie in movies:
        movie_id = movie["id"]
        title = movie["title"]
        thumbnail = movie["thumbnail"]

        if thumbnail:
            poster_url = f"data:image/jpeg;base64,{base64.b64encode(thumbnail).decode('utf-8')}"
        else:
            poster_url = "/static/default_poster.jpg"

        movies_list.append({"id": movie_id, "title": title, "poster_url": poster_url})

    conn.close()
    return jsonify(movies_list)

@app.route('/send_movie_invitation', methods=['POST'])
def send_movie_invitation():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 415

    sender_id = session.get('user_id')
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    movie_id = data.get('movie_id')

    if not receiver_id or not movie_id:
        return jsonify({"error": "Missing receiver or movie ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, file_path, video_url FROM movies WHERE id = %s", (movie_id,))  # Select video_url
    movie = cursor.fetchone()

    if not movie:
        return jsonify({"error": f"Invalid movie ID {movie_id}. Movie does not exist in the database."}), 400

    cursor.execute("INSERT INTO movie_rooms (movie_id) VALUES (%s)", (movie_id,))
    room_id = cursor.lastrowid

    cursor.execute("INSERT INTO movie_sessions (movie_id, sender_id, receiver_id, room_id) VALUES (%s, %s, %s, %s)",
                   (movie_id, sender_id, receiver_id, room_id))
    session_id = cursor.lastrowid

    cursor.execute("INSERT INTO movie_participants (session_id, user_id) VALUES (%s, %s)", (session_id, sender_id))

    cursor.execute("""
        INSERT INTO notifications (user_id, message, notification_type, related_id) 
        VALUES (%s, %s, 'movie_invitation', %s)
    """, (receiver_id, f"You have been invited to watch a movie!", session_id))

    conn.commit()
    conn.close()

    socketio.emit('movie_invitation', {
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'session_id': session_id,
        'movie_path': movie['file_path']
    }, room=receiver_id)
    print(f"Movie file path: {movie['file_path']}")
    return jsonify({
        "message": "Invitation sent",
        "session_id": session_id,
        "room_id": room_id,
        "movie_path": movie['file_path'].replace("\\", "/")  # Forward slashes!
    }), 200

@app.route('/join_movie_session', methods=['POST'])
def join_movie_session():
    user_id = session.get('user_id')
    data = request.get_json()
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({"error": "Missing session ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT movie_id, room_id FROM movie_sessions WHERE id = %s", (session_id,))
    session_data = cursor.fetchone()

    if not session_data:
        return jsonify({"error": "Session not found"}), 404

    # Add user to movie session
    cursor.execute("INSERT INTO movie_participants (session_id, user_id) VALUES (%s, %s)", (session_id, user_id))

    cursor.execute("SELECT file_path, video_url FROM movies WHERE id = %s",
                   (session_data['movie_id'],))  # Select video_url
    movie = cursor.fetchone()

    conn.commit()
    conn.close()
    print(f"Movie file path: {movie['file_path']}")
    return jsonify({
        "message": "Joined movie session",
        "room_id": session_data['room_id'],
        "movie_path": movie['file_path'],
        "video_url": movie.get('video_url')  # Return video_url
    }), 200


@socketio.on('join')  # Corrected event name
def on_join(data):
    room = data.get('room')
    if not room:
        print("Error: Missing 'room' key in data:", data)
        return

    username = data.get('username', 'Unknown')
    join_room(room)
    emit('status', {'msg': f'{username} has joined the room {room}.'}, room=room)


@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    emit('status', {'msg': f'{username} has left the room.'}, room=room)

@socketio.on('sync_playback')
def handle_sync_playback(data):
    emit('playback_update', data, room=data['room'])
def generate(filename):
    with open(filename, "rb") as f:
        while chunk := f.read(1024 * 1024):  # Read in chunks
            yield chunk

def get_movie_from_db(movie_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT title, file_path FROM movies WHERE id = %s"
    cursor.execute(query, (movie_id,))
    movie = cursor.fetchone()

    cursor.close()
    conn.close()

    if movie and movie["file_path"]:
        filename = movie["file_path"].replace("\\", "/")  # Ensure forward slashes for URL
        return {
            "title": movie["title"],
            "file_path": filename  # Only return the filename
        }
    return None


@app.route('/get_movie_details', methods=['GET'])
def get_movie_details():
    session_id = request.args.get('session_id')

    if not session_id:
        return jsonify({"error": "Missing session ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT movie_id, room_id FROM movie_sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()

    if not session:
        return jsonify({"error": "Session not found"}), 404

    cursor.execute("SELECT file_path FROM movies WHERE id = %s", (session['movie_id'],))
    movie = cursor.fetchone()

    conn.close()

    return jsonify({
        "message": "Movie session details retrieved",
        "room_id": session['room_id'],  # Ensure room_id is returned
        "movie_url": movie['file_path']
    }), 200


@app.route("/movies/<path:filename>")
def serve_movie(filename):
    file_path = os.path.join(EXTERNAL_HDD_PATH, filename)

    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    mime_type, _ = guess_type(file_path)
    return send_file(file_path, mimetype=mime_type or "video/mp4")



# Accept Movie Invitation
@app.route('/accept_movie_invitation', methods=['POST'])
def accept_movie_invitation():
    receiver_id = session.get('user_id')
    data = request.get_json()
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({"error": "Missing session ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get the session data
    cursor.execute("SELECT id, movie_id, room_id, sender_id FROM movie_sessions WHERE id = %s", (session_id,))
    session_data = cursor.fetchone()

    if not session_data:
        return jsonify({"error": "Session not found"}), 404

    cursor.execute("SELECT file_path FROM movies WHERE id = %s", (session_data['movie_id'],))
    movie = cursor.fetchone()

    if not movie:
        return jsonify({"error": "Movie not found"}), 404

    cursor.execute("INSERT INTO movie_participants (session_id, user_id) VALUES (%s, %s)", (session_id, receiver_id))

    cursor.execute("DELETE FROM notifications WHERE user_id = %s AND related_id = %s", (receiver_id, session_id))

    conn.commit()

    # Notify the sender
    sender_id = session_data['sender_id']  # Get sender ID from session data

    # Insert notification for the sender
    cursor.execute("INSERT INTO notifications (user_id, message, notification_type, related_id) "
                   "VALUES (%s, %s, %s, %s)",
                   (sender_id, f"{session.get('user')} has accepted your movie invitation!", "movie_invitation_accepted", session_id))
    conn.commit()

    conn.close()

    # Emit Socket.IO event to sender (if you are using Socket.IO)
    socketio.emit('movie_invitation_accepted', {'session_id': session_id, 'receiver_id': receiver_id}, room=f'user_{sender_id}')  # Notify sender
    # or
    # socketio.emit('movie_invitation_accepted', {'session_id': session_id, 'receiver_id': receiver_id, 'room_id': session_data['room_id']}, room=f'room_{session_data['room_id']}')  # Notify sender in the room

    return jsonify({
        "message": "You have joined the movie session!",
        "session_id": session_data['id'],
        "room_id": session_data['room_id'],
        "movie_path": movie['file_path'].replace("\\", "/")
    }), 200


@app.route('/create_movie_room', methods=['POST'])
def create_movie_room():
    sender_id = session.get('user_id')
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    movie_id = data.get('movie_id')

    if not receiver_id or not movie_id:
        return jsonify({"error": "Missing receiver or movie ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create a new movie room
    cursor.execute("INSERT INTO movie_rooms (movie_id) VALUES (%s)", (movie_id,))
    room_id = cursor.lastrowid

    # Add both sender and receiver to the room
    cursor.execute("INSERT INTO movie_participants (room_id, user_id) VALUES (%s, %s)", (room_id, sender_id))
    cursor.execute("INSERT INTO movie_participants (room_id, user_id) VALUES (%s, %s)", (room_id, receiver_id))

    # Send notification to the receiver
    cursor.execute("""
        INSERT INTO notifications (user_id, message, notification_type, related_id) 
        VALUES (%s, %s, 'movie_invitation', %s)
    """, (receiver_id, f"You have been invited to watch a movie!", room_id))

    conn.commit()
    conn.close()

    return jsonify({"message": "Invitation sent", "room_id": room_id}), 200


def get_receiver_socket(receiver_id):
    return user_sockets.get(receiver_id)
@socketio.on('join_room') # Corrected event name
def handle_join_room(data):
    room_id = data.get('room_id')  # Use `.get()` to safely access
    user_id = data.get('user_id')  # Use `.get()` to safely access

    if not room_id or not user_id:
        emit('error', {"message": "Missing room_id or user_id"})
        return

    # Store the user's socket ID
    user_sockets[user_id] = request.sid

    join_room(room_id)
    emit('room_message', {"message": f"User {user_id} joined room {room_id}"}, room=room_id)

@socketio.on('send_message')
def handle_send_message(data):
    room_id = data['room_id']
    message = data['message']
    sender_id = data['sender_id']

    # Fetch sender's username
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = %s", (sender_id,))
    user = cursor.fetchone()
    conn.close()

    sender = user['username'] if user else "Unknown"

    # Save message to the database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (room_id, sender_id, message) VALUES (%s, %s, %s)",
                   (room_id, sender_id, message))
    conn.commit()
    conn.close()

    # Emit the message to the room
    emit('receive_message', {'sender': sender, 'message': message}, room=room_id)


@socketio.on("sync_playback")
def sync_playback(data):
    print(f"Received sync_playback: {data}")  # ✅ Debugging
    session_id = data.get("session_id")
    time = data.get("time")
    playing = data.get("playing")

    if session_id:
        socketio.emit("playback_update", {
            "session_id": session_id,
            "time": time,
            "playing": playing
        }, room=session_id)


@socketio.on('send_message')
def send_message(data):
    session_id = data.get('session_id')
    message = data.get('message')
    sender_id = data.get('sender_id')  # Assuming you are sending the user ID in the data

    # Validate if receiver_id is in the data
    receiver_id = data.get('receiver_id')
    if not receiver_id:
        emit('error', {'message': 'Receiver ID is missing'})
        return

    # Fetch the sender's name or username from the database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = %s", (sender_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        sender = user['username']  # Or user['name'] if you want to use their full name
    else:
        sender = "Unknown"

    # Emit the message to all users in the session
    emit('receive_message', {'sender': sender, 'message': message}, room=session_id)

    # Emit the message to the specific receiver if available
    receiver_socket_id = get_receiver_socket(receiver_id)
    if receiver_socket_id:
        emit('receive_message', {'sender': sender, 'message': message}, room=receiver_socket_id)
    else:
        emit('error', {'message': 'Receiver not found or disconnected'})


@socketio.on("start_movie")
def start_movie(data):
    session_id = data.get("session_id")
    movie_id = data.get("movie_id")

    # Fetch the movie URL from the database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT video_url FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()
    conn.close()

    if movie:
        movie_url = movie["video_url"]
        emit("movie_started", {"movie_url": movie_url}, room=session_id)
    else:
        emit("error", {"message": "Movie not found"}, room=session_id)

@app.route('/notifications')
def get_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch notifications
    cursor.execute("SELECT id, message, notification_type, related_id FROM notifications WHERE user_id = %s", (user_id,))
    notifications = cursor.fetchall()

    for notif in notifications:
        if notif["notification_type"] == "movie_invitation":
            # ✅ Corrected the table and column names
            cursor.execute("SELECT room_id FROM movie_sessions WHERE id = %s", (notif["related_id"],))
            session_data = cursor.fetchone()
            if session_data:
                notif["session_id"] = session_data["room_id"]  # ✅ Assign room_id as session_id

    conn.close()
    return jsonify(notifications)

@socketio.on('disconnect')
def handle_disconnect():
    print("A user disconnected")


# Join Room via Socket.IO
# Dictionary to store user socket IDs
user_sockets = {}

@app.route('/get_chat_room_name', methods=['GET'])
def get_chat_room_name():
    user1 = min(int(request.args.get('user1')), int(request.args.get('user2')))
    user2 = max(int(request.args.get('user1')), int(request.args.get('user2')))
    room_name = f"chat_{user1}_{user2}"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_rooms WHERE room_name = %s", (room_name,)) # Select id
    result = cursor.fetchone()
    conn.close()

    if result:
        room_id = result['id'] # Get room_id
        return jsonify({"room_name": room_name, "room_id": room_id}), 200 # Send both
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_rooms (room_name) VALUES (%s)", (room_name,))
        conn.commit()
        room_id = cursor.lastrowid # Get newly created room_id
        conn.close()
        return jsonify({"room_name": room_name, "room_id": room_id}), 200 # Send both

@socketio.on('leave')
def handle_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    emit('room_message', {'message': f'{username} has left the room.'}, to=room)


@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    emit('joined', {'room': room}, to=request.sid)
    if room.startswith("chat_"):
        emit('message', {'username': username, 'message': f'{username} has joined the room.', 'room': room}, to=room)

@socketio.on('message')
def handle_message(data):
    print("Message received:", data)
    room_name = data['room']  # Get the room name
    username = data['username']
    message = data['message']
    user_id = get_user_id_from_username(username)

    if user_id:
        room_id = get_room_id_from_room_name(room_name)  # Get the room ID

        if room_id:  # Check if room_id was found
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO messages (room_id, sender_id, message) VALUES (%s, %s, %s)",
                               (room_id, user_id, message))  # Use room_id (integer)
                conn.commit()
                emit('message', data, to=room_name)  # Emit using room_name
            except Exception as e:
                print(f"Error storing message: {e}")
                conn.rollback()
            finally:
                conn.close()
        else:
            print(f"Room ID not found for room name: {room_name}")
            # Handle the error, maybe emit an error message to the client

    else:
        print("User ID not found for username:", username)


def get_user_id_from_username(username):  # Make sure this function is defined
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if user:
            return user['id']
        else:
            return None
    finally:
        conn.close()

def get_room_id_from_room_name(room_name): # This also needs to be defined
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM chat_rooms WHERE room_name = %s", (room_name,))
        room = cursor.fetchone()
        if room:
            return room['id']
        else:
            return None
    finally:
        conn.close()

@app.route('/get_messages/<int:room_id>')
def get_messages(room_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT u.username, m.message FROM messages m JOIN users u ON m.sender_id = u.id WHERE m.room_id = %s ORDER BY m.timestamp ASC", (room_id,))
        messages = cursor.fetchall()
        message_list = []
        for message in messages:
            message_list.append({'sender': message['username'], 'message': message['message']})

        return jsonify(message_list)
    except Exception as e:
        print(f"Error fetching messages: {e}")
        return jsonify([]) # Return empty array in case of error
    finally:
        conn.close()

# Sync Movie Playback via Socket.IO
@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    username = session.get('user')
    if username:
        connection = get_db_connection()
        try:
            # Update session_active in the database
            update_query = "UPDATE users SET session_active = 0 WHERE username = %s"
            with connection.cursor() as cursor:
                cursor.execute(update_query, (username,))
            connection.commit()
        except Exception as e:
            print(f"Error updating logout status: {e}")
        finally:
            connection.close()

    # Clear session
    session.clear()
    # Ensure subscriptions are untouched during logout
    assert 'user_id' not in session or has_active_subscription(session['user_id']) is not None
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.before_request
def check_session():
    if 'user' not in session and request.endpoint not in ['login', 'register', 'static']:
        return redirect(url_for('login'))


@app.route('/active_users')
def active_users():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query = "SELECT username, email, role FROM users WHERE session_active = 1"
            cursor.execute(query)
            active_users = cursor.fetchall()
        return render_template('active_users.html', active_users=active_users)
    except Exception as e:
        print(f"Error fetching active users: {e}")
        flash("An error occurred while fetching active users.", "error")
        return redirect(url_for('admin_page'))
    finally:
        connection.close()


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form['name']
            username = request.form['username']
            password = request.form['password']
            dob = request.form['dob']
            email = request.form['email']  # Get email from the form
            profile_image = request.files['profile_image']

            # Validate inputs (add email validation if needed)
            if not (name and username and password and dob and email and profile_image):
                flash("All fields are required!")
                return redirect(url_for('register'))

            # Read profile image data
            profile_image_data = profile_image.read()

            # Save to database (include email)
            connection = get_db_connection()
            with connection.cursor() as cursor:
                query = """
                                INSERT INTO users (name, username, password, dob, email, profile_image)  -- Added email to query
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """
                cursor.execute(query,
                               (name, username, password, dob, email, profile_image_data))  # Added email to values
                connection.commit()

                # Get the newly registered user's ID
                new_user_id = cursor.lastrowid

                # Add free trial subscription
                start_date = datetime.now().date()
                end_date = start_date + timedelta(days=7)  # 7 days free trial
                cursor.execute("""
                                INSERT INTO user_subscriptions (user_id, subscription_id, start_date, end_date) 
                                VALUES (%s, 1, %s, %s)  -- Assuming subscription ID 1 is the free trial
                            """, (new_user_id, start_date, end_date))
                connection.commit()

                # Send welcome email with free trial details
                send_welcome_email(email)

            flash("Registration successful! You have a 7-day free trial.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            print(f"Error occurred: {e}")
            flash("An error occurred during registration.")
        finally:
            connection.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                # Fetch user details
                query = "SELECT * FROM users WHERE username=%s"
                cursor.execute(query, (username,))
                user = cursor.fetchone()

            if user and user['password'] == password:  # Replace with hashing logic
                session['user'] = user['username']
                session['is_admin'] = user.get('is_admin', False)
                session['username'] = user['username']
                session['user_id'] = user['id']

                # Check for active subscription.css
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT end_date
                        FROM user_subscriptions
                        WHERE user_id = %s AND end_date >= CURDATE()
                        LIMIT 1
                    """, (user['id'],))
                    subscription = cursor.fetchone()

                if subscription:
                    session['subscription_end_date'] = subscription['end_date']
                    session['user_id'] = user['id']  # Store user ID in session for further checks

                # Update session_active in the database
                update_query = "UPDATE users SET session_active = 1 WHERE username = %s"
                with connection.cursor() as cursor:
                    cursor.execute(update_query, (username,))
                connection.commit()

                if user.get('is_admin'):
                    return redirect(url_for('admin_page'))
                else:
                    return redirect(url_for('dashboard', username=username))
            else:
                flash("Invalid username or password", "error")  # Display an error message

        except Exception as e:
            print(f"Error occurred: {e}")
            flash("An error occurred during login.", "error")  # Display a general error message
        finally:
            connection.close()

    return render_template('login.html')

@app.before_request
def before_request():
    try:
        print(f"Session Data: {dict(session)}")  # Convert session to dict for safe printing
    except Exception as e:
        print(f"Error accessing session: {e}")

@app.route('/admin_page')
def admin_page():
    if not session.get('is_admin'):
        flash('You must be an admin to access this page')
        return redirect(url_for('login'))

    return render_template('admin.html')

@app.route('/edit_profile/<username>', methods=['GET', 'POST'])
def edit_profile(username):
    connection = get_db_connection()

    try:
        # Fetch user details based on username
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()

        if not user:
            flash("User not found.")
            return redirect(url_for('login'))

        if request.method == 'POST':
            # Get updated details from form
            name = request.form['name']
            dob = request.form['dob']
            email = request.form['email']
            profile_image = request.files.get('profile_image')  # Optional: Upload a new profile image

            # Handle profile image upload (if provided)
            if profile_image:
                profile_image_data = profile_image.read()
            else:
                profile_image_data = user['profile_image']  # Keep existing image if none uploaded

            # Update user profile in the database
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE users
                    SET name = %s, dob = %s, email = %s, profile_image = %s
                    WHERE username = %s
                """, (name, dob, email, profile_image_data, username))
                connection.commit()

            flash("Profile updated successfully!", "success")
            return redirect(url_for('dashboard', username=username))

        return render_template('edit_profile.html', user=user)

    except Exception as e:
        print(f"Error occurred: {e}")
        flash("An error occurred while updating your profile.")
        return redirect(url_for('dashboard', username=username))

    finally:
        connection.close()


@app.route('/dashboard')
def dashboard():
    username = request.args.get('username')

    if not username:
        flash("You need to be logged in to access the dashboard.")
        return redirect(url_for('login'))

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            user = cursor.fetchone()

            if not user:
                flash("User not found.")
                return redirect(url_for('login'))

            dob = user['dob']
            dob_date = dob
            age = (datetime.now().date() - dob_date).days // 365

            if age >= 18:
                query = "SELECT id, title, thumbnail, category, language, release_date, file_path FROM movies"
                category = request.args.get('category', 'normal')
                if category != 'normal':
                    query += " WHERE category = %s"
                    cursor.execute(query, (category,))
                else:
                    cursor.execute(query)
            else:
                cursor.execute("""
                    SELECT id, title, thumbnail, category, language, release_date, file_path 
                    FROM movies 
                    WHERE category = 'normal'
                """)
            movies = cursor.fetchall()

        # Fetch subscription.css details from session
        subscription_end_date_str = session.get('subscription_end_date')

        remaining_days = None  # Initialize to None

        if subscription_end_date_str:
            try:  # Handle potential parsing errors
                subscription_end_date = datetime.strptime(subscription_end_date_str, "%a, %d %b %Y %H:%M:%S GMT").date()
                remaining_days = (subscription_end_date - datetime.now().date()).days

                if remaining_days is not None and remaining_days < 0:  # Check if remaining_days is not none before comparing
                    remaining_days = 0  # or a message like "Subscription expired"

            except ValueError as e:  # Catch datetime parsing errors
                print(f"Error parsing date: {e}")
                flash("Error processing subscription details.", "error") # If no subscription.css end date, set to 0

        # Convert movie thumbnails to base64
        for movie in movies:
            if movie['thumbnail']:
                movie['thumbnail'] = base64.b64encode(movie['thumbnail']).decode('utf-8')

        if user.get('profile_image'):
            user['profile_image'] = base64.b64encode(user['profile_image']).decode('utf-8')

        movie_sections = {}

        # Categorize movies by New Releases
        new_release_movies = [movie for movie in movies if
                              movie['release_date'] and (datetime.now().date() - movie['release_date']).days <= 30]
        if new_release_movies:
            movie_sections['New Releases'] = new_release_movies

        # Categorize movies by language
        languages = set(movie['language'] for movie in movies)
        for language in languages:
            movies_in_language = [movie for movie in movies if
                                  movie['language'] == language]
            if movies_in_language:
                movie_sections[language] = movies_in_language

        return render_template('dashboard.html', movies=movies, user=user, movie_sections=movie_sections, remaining_days=remaining_days)

    except Exception as e:
        print(f"Error occurred: {e}")
        flash("An error occurred while loading the dashboard.")
        return redirect(url_for('login'))

    finally:
        connection.close()


def send_welcome_email(user_email):
    sender_email = "spotnet432@gmail.com"  # Replace with your email
    sender_password = "remb cmks dxlc homi"  # Replace with your email password

    message = MIMEMultipart("alternative")
    message["Subject"] = "Welcome to SpotNet - Your Free Trial is Active!"
    message["From"] = sender_email
    message["To"] = user_email

    html = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; line-height: 1.5; padding: 20px; background-color: #f4f4f4; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #2b5f97;">Welcome to SpotNet!</h2>
            <p>Thank you for joining SpotNet. Your 7-day free trial has begun!</p>
            <p>Explore our vast collection of movies and songs. Enjoy unlimited streaming and downloads during your trial period.</p>
            <p>If you have any questions, feel free to contact us at support@spotnet.com.</p>
            <div style="text-align: center; margin-top: 20px;">
                <img src="https://your-logo-url.com/logo.png" alt="SpotNet Logo" style="max-width: 150px;">
            </div>
        </div>
    </body>
    </html>
    """

    # Attach HTML content
    message.attach(MIMEText(html, "html"))

    # Send the email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, user_email, message.as_string())

# Function to update user preferences based on the most recent activities
def update_user_preferences():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Modify query to ignore NULL genres
            sql_query = """
                INSERT INTO user_preferences (user_id, genre, last_updated)
                SELECT user_activity.user_id, movies.genre, NOW()
                FROM user_activity
                JOIN movies ON movies.id = user_activity.movie_id
                WHERE user_activity.timestamp > NOW() - INTERVAL 1 DAY
                AND movies.genre IS NOT NULL  -- Ignore NULL genres
                ON DUPLICATE KEY UPDATE genre = movies.genre, last_updated = NOW()
            """
            print(f"Executing SQL: {sql_query}")
            cursor.execute(sql_query)
            connection.commit()

            print("User preferences updated.")
    except Exception as e:
        print(f"Error updating preferences: {e}")
    finally:
        connection.close()


# Scheduler to update preferences every minute
scheduler = BackgroundScheduler()
scheduler.add_job(update_user_preferences, IntervalTrigger(seconds=60))  # Update every minute
scheduler.start()

@app.route('/user_activity', methods=['POST'])
def user_activity():
    # Get the data from the request
    user_id = request.json.get('user_id')
    movie_id = request.json.get('movie_id')
    activity_type = request.json.get('activity_type')  # 'watch', 'like', 'rate', 'comment'

    # Validate the activity_type
    if activity_type not in ['watch', 'like', 'rate', 'comment']:
        return jsonify({'error': 'Invalid activity type'}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check if the activity already exists
            cursor.execute("""
                SELECT * FROM user_activity 
                WHERE user_id = %s AND movie_id = %s
            """, (user_id, movie_id))
            existing_activity = cursor.fetchone()

            if existing_activity:
                # Update the existing activity
                cursor.execute("""
                    UPDATE user_activity
                    SET activity_type = %s, timestamp = NOW()
                    WHERE user_id = %s AND movie_id = %s
                """, (activity_type, user_id, movie_id))
            else:
                # Insert new activity
                cursor.execute("""
                    INSERT INTO user_activity (user_id, movie_id, activity_type, timestamp)
                    VALUES (%s, %s, %s, NOW())
                """, (user_id, movie_id, activity_type))

            # If the activity is a rating or comment, update user preferences
            if activity_type in ['rate', 'comment']:
                cursor.execute("""
                    SELECT genre FROM movies WHERE id = %s
                """, (movie_id,))
                movie_genre = cursor.fetchone()

                if movie_genre and movie_genre['genre']:  # Ensure genre is not NULL
                    cursor.execute("""
                        INSERT INTO user_preferences (user_id, genre)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE genre = %s
                    """, (user_id, movie_genre['genre'], movie_genre['genre']))

            connection.commit()

        return jsonify({'message': 'Activity updated successfully'}), 200

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({'error': 'An error occurred while updating activity.'}), 500

    finally:
        connection.close()

@app.route('/recommendations', methods=['GET'])
def recommendations():
    user_id = request.args.get('user_id')

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Get the user's preferred genres from user_preferences
            cursor.execute("SELECT genre FROM user_preferences WHERE user_id = %s", (user_id,))
            preferred_genres = cursor.fetchall()

            # If no preferences, recommend random movies
            if not preferred_genres:
                cursor.execute("SELECT id, title, genre, thumbnail FROM movies ORDER BY RAND() LIMIT 5")
                recommended_movies = cursor.fetchall()
            else:
                # Extract genres from the fetched results
                genres = [genre['genre'] for genre in preferred_genres]

                # Use prepared statements to safely insert the list of genres into the query
                placeholders = ', '.join(['%s'] * len(genres))
                query = f"""
                    SELECT id, title, genre, thumbnail 
                    FROM movies 
                    WHERE genre IN ({placeholders})
                    ORDER BY RAND() LIMIT 5
                """
                cursor.execute(query, genres)
                recommended_movies = cursor.fetchall()

            # Convert movie thumbnails to base64 for frontend display
            for movie in recommended_movies:
                if movie['thumbnail']:
                    movie['thumbnail'] = base64.b64encode(movie['thumbnail']).decode('utf-8')

            # Get recommended songs (similar to movie recommendations)
            cursor.execute("""
                SELECT songs.id, songs.title, movies.thumbnail FROM songs
                LEFT JOIN movies ON songs.movie_id = movies.id
                ORDER BY RAND() LIMIT 5
            """)
            recommended_songs = cursor.fetchall()

            # Convert song thumbnails to base64 for frontend display
            for song in recommended_songs:
                if song['thumbnail']:
                    song['thumbnail'] = base64.b64encode(song['thumbnail']).decode('utf-8')

        return jsonify({'movies': recommended_movies, 'songs': recommended_songs})

    except Exception as e:
        print(f"Error occurred during recommendation: {e}")
        return jsonify({'error': 'An error occurred while fetching recommendations.'}), 500

    finally:
        connection.close()
@app.route('/retrieve_carousel_images', methods=['GET'])
def retrieve_carousel_images():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT image_data, movie_id FROM carousel_images")  # Ensure movie_id is included
            images = cursor.fetchall()
            # Convert the binary image data into base64 encoding for embedding in HTML
            image_data_base64 = [
                {'image': base64.b64encode(image['image_data']).decode('utf-8'), 'movie_id': image['movie_id']}
                for image in images
            ]
            return jsonify({'images': image_data_base64})
    finally:
        connection.close()

@app.route('/admin/get_movies', methods=['GET'])
def get_movies():
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, title FROM movies")  # Adjust query if needed
            movies = cursor.fetchall()
        connection.close()
        return jsonify(movies)
    except Exception as e:
        print(f"Error fetching movies: {e}")
        return jsonify({'error': 'Could not fetch movies'}), 500


@app.route('/admin/get_carousel_images', methods=['GET'])
def get_carousel_images():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Modify the query to include movie title
            cursor.execute("""
                SELECT carousel_images.id, carousel_images.image_data, movies.title AS movie_title
                FROM carousel_images
                LEFT JOIN movies ON carousel_images.movie_id = movies.id
            """)
            images = cursor.fetchall()

        # Convert image data to base64 and include the ID and movie title
        image_data = [{'id': image['id'], 'image': base64.b64encode(image['image_data']).decode('utf-8'), 'movie_title': image['movie_title']} for image in images]

        return jsonify({'images': image_data})
    finally:
        connection.close()

@app.route('/admin/add_carousel_image', methods=['POST'])
def add_carousel_image():
    try:
        image_file = request.files.get('image')
        genre = request.form.get('genre')  # Get genre from the form data
        movie_id = request.form.get('movie_id')  # Get movie ID from the form data

        if image_file and genre and movie_id:
            image_data = image_file.read()
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO carousel_images (image_data, genre, movie_id) VALUES (%s, %s, %s)",
                    (image_data, genre, movie_id)
                )
                connection.commit()
            connection.close()
            return jsonify({'message': 'Image added successfully'}), 200
        else:
            return jsonify({'error': 'Missing image, genre, or movie ID'}), 400
    except Exception as e:
        print(f"Error adding image: {e}")
        return jsonify({'error': 'Could not add image'}), 500

@app.route('/admin/delete_carousel_image/<int:image_id>', methods=['DELETE'])
def delete_carousel_image(image_id):
    try:
        # Check if the image exists
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM carousel_images WHERE id = %s", (image_id,))
            image = cursor.fetchone()
            if image:
                cursor.execute("DELETE FROM carousel_images WHERE id = %s", (image_id,))
                connection.commit()
                return jsonify({'message': 'Image deleted successfully'}), 200
            else:
                return jsonify({'error': 'Image not found'}), 404
    except Exception as e:
        print(f"Error deleting image: {e}")
        return jsonify({'error': 'Could not delete image'}), 500
    finally:
        connection.close()

@app.route('/search_movies')
def search_movies():
    query = request.args.get('query', '').lower()

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Search movies
            movie_query = """
                SELECT id, title, thumbnail 
                FROM movies 
                WHERE LOWER(title) LIKE %s
            """
            cursor.execute(movie_query, (f"%{query}%",))
            movies = cursor.fetchall()

            # Convert movie thumbnails to base64
            for movie in movies:
                if movie['thumbnail']:
                    movie['thumbnail'] = base64.b64encode(movie['thumbnail']).decode('utf-8')

            # Search songs
            song_query = """
                SELECT songs.id, songs.title, movies.thumbnail 
                FROM songs
                LEFT JOIN movies ON songs.movie_id = movies.id
                WHERE LOWER(songs.title) LIKE %s
            """
            cursor.execute(song_query, (f"%{query}%",))
            songs = cursor.fetchall()

            # Convert movie thumbnails for songs to base64
            for song in songs:
                if song['thumbnail']:
                    song['thumbnail'] = base64.b64encode(song['thumbnail']).decode('utf-8')

        return jsonify({'movies': movies, 'songs': songs})

    except Exception as e:
        print(f"Error occurred during search: {e}")
        return jsonify({'error': 'An error occurred during the search.'}), 500

    finally:
        connection.close()


@app.route('/live_movie_page')
def live_movie_page():
    # Static URL for streaming
    m3u8_url = "http://127.0.0.1/hls/test/index.m3u8"  # Ensure this URL is correct

    # Render the page with the streaming URL
    return render_template('live_movie_page.html', m3u8_url=m3u8_url)


@app.route('/admin/select_live_movie', methods=['POST'])
def select_live_movie():
    if not session.get('is_admin'):
        flash('You must be an admin to access this page')
        return redirect(url_for('login'))

    movie_id = request.form['movie_id']
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM movies WHERE id=%s", (movie_id,))
            movie = cursor.fetchone()

        if movie:
            session['live_movie'] = movie_id
            flash(f'Now streaming: {movie["title"]}')
            return redirect(url_for('live_movie_page'))
        else:
            flash("Movie not found.")
            return redirect(url_for('live_movie_admin'))

    except Exception as e:
        flash("An error occurred while selecting the live movie.")
        return redirect(url_for('admin_page'))
    finally:
        connection.close()



# WebSocket connection for real-time communication
@socketio.on('connect')
def handle_connect():
    print('A user has connected.')

@socketio.on('movie_forward')
def handle_movie_forward(data):
    # Move forward 10 seconds or any other logic
    print('Movie Forward:', data)
    socketio.emit('movie_forward', {'action': 'forward'}, broadcast=True)

@socketio.on('movie_backward')
def handle_movie_backward(data):
    # Move backward 10 seconds or any other logic
    print('Movie Backward:', data)
    socketio.emit('movie_backward', {'action': 'backward'}, broadcast=True)

@socketio.on('movie_pause')
def handle_movie_pause(data):
    # Pause the movie
    print('Movie Pause:', data)
    socketio.emit('movie_pause', {'action': 'pause'}, broadcast=True)

@socketio.on('movie_play')
def handle_movie_play(data):
    # Play the movie
    print('Movie Play:', data)
    socketio.emit('movie_play', {'action': 'play'}, broadcast=True)


@app.route('/admin/live_movie')
def live_movie_admin():
    if not session.get('is_admin'):
        flash('You must be an admin to access this page')
        return redirect(url_for('login'))

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM movies")
            movies = cursor.fetchall()

        return render_template('live_movie_admin.html', movies=movies)
    except Exception as e:
        flash("An error occurred while fetching movies.")
        return redirect(url_for('admin_page'))
    finally:
        connection.close()


@app.route('/admin/movie_control', methods=['POST'])
def movie_control():
    action = request.form.get('action')  # 'pause', 'play', 'forward', 'backward'

    if action == 'forward':
        socketio.emit('movie_forward', {'action': 'forward'}, room=True)
    elif action == 'backward':
        socketio.emit('movie_backward', {'action': 'backward'}, room=True)
    elif action == 'pause':
        socketio.emit('movie_pause', {'action': 'pause'}, room=True)
    elif action == 'play':
        socketio.emit('movie_play', {'action': 'play'}, room=True)

    return redirect(url_for('live_movie_page'))


@app.route('/stream_movie/<int:movie_id>')
def stream_movie(movie_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT live_stream_url FROM movies WHERE id=%s", (movie_id,))
            movie = cursor.fetchone()

        if not movie:
            flash("Movie not found.")
            return redirect(url_for('dashboard'))

        if movie['live_stream_url']:
            # If there's a live stream URL, use it
            return redirect(movie['live_stream_url'])
        else:
            flash("No stream available for this movie.")
            return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Error occurred: {e}")
        flash("An error occurred while streaming the movie.")
        return redirect(url_for('dashboard'))
    finally:
        connection.close()

@app.route('/admin/stats', methods=['GET'])
def fetch_stats():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Fetch total movies
            cursor.execute("SELECT COUNT(*) AS total_movies FROM movies")
            total_movies = cursor.fetchone()["total_movies"]

            # Fetch total songs
            cursor.execute("SELECT COUNT(*) AS total_songs FROM songs")
            total_songs = cursor.fetchone()["total_songs"]

            # Fetch total users
            cursor.execute("SELECT COUNT(*) AS total_users FROM users")
            total_users = cursor.fetchone()["total_users"]

        return jsonify({
            "total_movies": total_movies,
            "total_songs": total_songs,
            "total_users": total_users
        })
    finally:
        connection.close()

# Fetch Users Route
@app.route('/admin/users', methods=['GET'])
def get_users():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, username, email, role FROM users")
            users = cursor.fetchall()
        return jsonify(users)
    finally:
        connection.close()

# Add User Route
@app.route('/admin/users', methods=['POST'])
def add_user():
    data = request.json
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (username, email, role) 
                VALUES (%s, %s, %s)
                """,
                (
                    data['username'],
                    data['email'],
                    data['role']
                )
            )
            connection.commit()
        return jsonify({"message": "User added successfully"}), 201
    finally:
        connection.close()

# Edit User Route
@app.route('/admin/users/<int:user_id>', methods=['GET', 'PUT'])
def edit_user(user_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if request.method == 'GET':
                cursor.execute("SELECT id, username, email, role FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                return jsonify(user)
            elif request.method == 'PUT':
                data = request.json
                cursor.execute(
                    """
                    UPDATE users 
                    SET username = %s, email = %s, role = %s 
                    WHERE id = %s
                    """,
                    (
                        data['username'],
                        data['email'],
                        data['role'],
                        user_id
                    )
                )
                connection.commit()
                return jsonify({"message": "User updated successfully"})
    finally:
        connection.close()

# Delete User Route
@app.route('/admin/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            connection.commit()
        return jsonify({"message": "User deleted successfully"})
    finally:
        connection.close()



# Admin manage users page
@app.route('/admin/manage_users')
def manage_users():
    return render_template('manage_users.html')



if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
