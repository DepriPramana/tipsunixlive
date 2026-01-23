-- Add music_playlist_id column to scheduled_lives table
-- Execute this SQL in your database to add music playlist scheduling support

ALTER TABLE scheduled_lives
ADD COLUMN music_playlist_id INTEGER REFERENCES music_playlists(id);

-- Verify the column was added
-- SELECT music_playlist_id FROM scheduled_lives LIMIT 1;
