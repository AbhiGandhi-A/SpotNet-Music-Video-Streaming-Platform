from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
import pymysql
import base64
import os
from io import BytesIO
import sqlite3
from datetime import datetime
from flask import session
from dotenv import load_dotenv
load_dotenv()  # This will load variables from .env file into the environment


app = Flask(__name__)
app.secret_key = "spotnet"




# Database connection
def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306)),  # Default port is 3306
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10  # Timeout after 10 seconds
    )



# Routes

@app.route('/movie/<int:movie_id>/play')
def play_movie(movie_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT video_file FROM movies WHERE id=%s", (movie_id,))
        movie = cursor.fetchone()

    connection.close()

    if movie and movie['video_file']:
        return send_file(BytesIO(movie['video_file']), mimetype='video/mp4')
    return jsonify({'error': 'Movie not found'}), 404

@app.route('/song/<int:song_id>/play')
def play_song(song_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT song_file FROM songs WHERE id=%s", (song_id,))
        song = cursor.fetchone()

    connection.close()

    if song and song['song_file']:
        return send_file(BytesIO(song['song_file']), mimetype='audio/mpeg')
    return jsonify({'error': 'Song not found'}), 404


@app.route('/song/<int:song_id>/download')
def download_song(song_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT song_file, id FROM songs WHERE id=%s", (song_id,))
        song = cursor.fetchone()

    connection.close()

    if song and song['song_file']:
        filename = f"song_{song['id']}.mp3"  # You can change the extension based on the song format
        return send_file(
            BytesIO(song['song_file']),
            as_attachment=True,
            download_name=filename,
            mimetype='audio/mpeg'  # Update with the correct MIME type for the song format
        )
    return jsonify({'error': 'Song not found'}), 404


@app.route('/movie/<int:movie_id>/download')
def download_movie(movie_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT video_file, title FROM movies WHERE id=%s", (movie_id,))
        movie = cursor.fetchone()

    connection.close()

    if movie and movie['video_file']:
        filename = f"{movie['title']}.mp4"
        return send_file(
            BytesIO(movie['video_file']),
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4'
        )
    return jsonify({'error': 'Movie not found'}), 404


@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        # Fetch movie details
        cursor.execute("SELECT * FROM movies WHERE id=%s", (movie_id,))
        movie = cursor.fetchone()

        # Fetch ratings and comments for the movie
        cursor.execute("SELECT * FROM ratings WHERE movie_id=%s", (movie_id,))
        ratings = cursor.fetchall()

        cursor.execute("SELECT * FROM comments WHERE movie_id=%s", (movie_id,))
        comments = cursor.fetchall()

        # Fetch songs associated with the movie
        cursor.execute("SELECT * FROM songs WHERE movie_id=%s", (movie_id,))
        songs = cursor.fetchall()

    connection.close()

    # Convert movie thumbnail from binary data to base64 for display
    if movie and movie['thumbnail']:
        movie['thumbnail'] = base64.b64encode(movie['thumbnail']).decode('utf-8')

    return render_template('movie_details.html', movie=movie, ratings=ratings, comments=comments, songs=songs)

@app.route('/view_movie/<int:movie_id>')
def view_movie(movie_id):
    # Fetch the movie details from the database using the movie_id
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
        movie = cursor.fetchone()
    connection.close()

    # If movie is found, render the movie details page
    if movie:
        return render_template('view_movie.html', movie=movie)
    else:
        flash("Movie not found!")
        return redirect(url_for('movies_page'))


@app.route('/add_movie', methods=['GET', 'POST'])
def add_movie():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        visibility = request.form['visibility']
        category = request.form['category']  # Get category value from the form
        language = request.form['language']  # Get language value from the form
        release_date = request.form['release_date']  # Get release date from the form

        movie_file = request.files['movie_file']
        movie_data = movie_file.read()

        thumbnail_file = request.files['thumbnail_file']
        thumbnail_data = thumbnail_file.read()

        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = """
                INSERT INTO movies (title, description, thumbnail, video_file, visibility, category, language, release_date) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
            title, description, thumbnail_data, movie_data, visibility, category, language, release_date))
            connection.commit()
        connection.close()

        flash("Movie added successfully!")
        return redirect(url_for('dashboard'))

    return render_template('add_movie.html')


@app.route('/add_song', methods=['GET', 'POST'])
def add_song():
    connection = get_db_connection()

    if request.method == 'POST':
        movie_id = request.form['movie_id']  # Get movie_id from form
        song_file = request.files['song_file']
        song_data = song_file.read()
        language = request.form['language']  # Get language from form
        release_date = request.form['release_date']  # Get release date from form

        # Insert song into the database
        with connection.cursor() as cursor:
            query = """
                INSERT INTO songs (movie_id, song_file, language, release_date) 
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (movie_id, song_data, language, release_date))
            connection.commit()

        flash("Song added successfully!")
        return redirect(url_for('dashboard'))

    # Fetch movies from the database for the dropdown list
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, title FROM movies")
        movies = cursor.fetchall()

    connection.close()

    return render_template('add_song.html', movies=movies)


@app.route('/movies_page')
def movies_page():
    category = request.args.get('category', 'normal')
    language = request.args.get('language', '')
    release_date = request.args.get('release_date', '')

    connection = get_db_connection()

    query = "SELECT id, title, thumbnail, category, language, release_date FROM movies WHERE 1=1"

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
        movies = cursor.fetchall()

    connection.close()

    # Convert movie thumbnails from binary data to base64 for display
    for movie in movies:
        if movie['thumbnail']:
            movie['thumbnail'] = base64.b64encode(movie['thumbnail']).decode('utf-8')

    return render_template('movies_page.html', movies=movies)


@app.route('/songs_page')
def songs_page():
    category = request.args.get('category', 'normal')
    language = request.args.get('language', '')
    release_date = request.args.get('release_date', '')

    connection = get_db_connection()

    query = "SELECT id, title, category, language, release_date FROM songs WHERE 1=1"

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

    connection.close()

    return render_template('songs_page.html', songs=songs)


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


@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    """Logout the user and redirect to the login page"""
    session.pop('user', None)  # Remove the user session data
    flash("You have been logged out successfully!")
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form['name']
            username = request.form['username']
            password = request.form['password']
            dob = request.form['dob']
            profile_image = request.files['profile_image']

            # Validate inputs
            if not (name and username and password and dob and profile_image):
                flash("All fields are required!")
                return redirect(url_for('register'))

            # Read profile image data
            profile_image_data = profile_image.read()

            # Save to database
            connection = get_db_connection()
            with connection.cursor() as cursor:
                query = """
                    INSERT INTO users (name, username, password, dob, profile_image) 
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (name, username, password, dob, profile_image_data))
                connection.commit()

            flash("Registration successful!")
            return redirect(url_for('login'))

        except Exception as e:
            print(f"Error occurred: {e}")
            flash("An error occurred during registration.")
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = "SELECT * FROM users WHERE username=%s AND password=%s"
            cursor.execute(query, (username, password))
            user = cursor.fetchone()
        connection.close()
        if user:
            # Set the session data for the logged-in user
            session['user'] = user['username']  # Storing the username or any other identifier
            return redirect(url_for('dashboard', username=username))
        else:
            flash("Invalid username or password")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    category = request.args.get('category', 'normal')  # Default to 'normal' category if none selected
    username = request.args.get('username')
    connection = get_db_connection()

    # First cursor for fetching user data
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        if not user:
            flash("User not found.")
            return redirect(url_for('login'))

        # Get the user's date of birth and calculate age
        dob = user['dob']
        dob_date = dob
        age = (datetime.now().date() - dob_date).days // 365

        # Fetch movies based on age and category filters
        if age >= 18:
            query = "SELECT id, title, thumbnail, category, language, release_date FROM movies"
            if category != 'normal':
                query += " WHERE category = %s"
                cursor.execute(query, (category,))
            else:
                cursor.execute(query)
        else:
            cursor.execute("""
                SELECT id, title, thumbnail, category, language, release_date 
                FROM movies 
                WHERE category = 'normal'
            """)
        movies = cursor.fetchall()

    # Second cursor for fetching songs
    with connection.cursor() as cursor:
        query = "SELECT id, title, category, language, release_date FROM songs"
        if category != 'normal':
            query += " WHERE category = %s"
            cursor.execute(query, (category,))
        else:
            cursor.execute(query)
        songs = cursor.fetchall()

    connection.close()

    # Convert movie thumbnails from binary data to base64 for display
    for movie in movies:
        if movie['thumbnail']:
            movie['thumbnail'] = base64.b64encode(movie['thumbnail']).decode('utf-8')

    # Convert profile image to base64 (if it exists)
    if user.get('profile_image'):
        user['profile_image'] = base64.b64encode(user['profile_image']).decode('utf-8')

    # Categorize movies by language and release date
    new_releases = [movie for movie in movies if movie['release_date'] and (datetime.now().date() - movie['release_date']).days <= 30]
    hindi_movies = [movie for movie in movies if movie['language'] and movie['language'].lower() == 'hindi']
    gujarati_movies = [movie for movie in movies if movie['language'] and movie['language'].lower() == 'gujarati']

    return render_template('dashboard.html', movies=movies, user=user, new_releases=new_releases, hindi_movies=hindi_movies, gujarati_movies=gujarati_movies)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

