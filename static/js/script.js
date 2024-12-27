// Function to handle showing movie details when a movie card is clicked
function showMovieDetails(movieId) {
    // Fetch movie details from the server using the provided movieId
    fetch(`/movie-details/${movieId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json(); // Parse the response as JSON
        })
        .then(data => {
            // Update the movie title and video URL
            const movieTitleElement = document.getElementById('movie-title');
            const movieVideoElement = document.getElementById('movie-video');
            movieTitleElement.innerText = data.title || 'No title available';
            movieVideoElement.src = data.video_url || '';

            // Update the song list
            const songListElement = document.getElementById('song-list');
            songListElement.innerHTML = ''; // Clear the current song list

            if (Array.isArray(data.songs) && data.songs.length > 0) {
                data.songs.forEach(song => {
                    const songItem = document.createElement('div');
                    songItem.className = 'song-item';
                    songItem.innerText = song.title || 'Unknown Song'; // Display the song title

                    // Optional: Add a play button or other features for the song
                    const playButton = document.createElement('button');
                    playButton.innerText = 'Play';
                    playButton.className = 'play-button';
                    playButton.addEventListener('click', () => {
                        console.log(`Playing song: ${song.title}`);
                        // Logic to play the song can be added here
                    });

                    songItem.appendChild(playButton);
                    songListElement.appendChild(songItem); // Add the song to the song list
                });
            } else {
                const noSongsMessage = document.createElement('p');
                noSongsMessage.innerText = 'No songs available for this movie.';
                noSongsMessage.className = 'no-songs-message';
                songListElement.appendChild(noSongsMessage);
            }

            // Show the movie details section
            const movieDetailsElement = document.getElementById('movie-details');
            movieDetailsElement.style.display = 'block';
        })
        .catch(error => {
            console.error('Error fetching movie details:', error);

            // Optional: Display an error message to the user
            const movieDetailsElement = document.getElementById('movie-details');
            movieDetailsElement.style.display = 'none'; // Hide details on error
            alert('Failed to load movie details. Please try again later.');
        });
}
