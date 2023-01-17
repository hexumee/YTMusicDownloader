# YTMusicDownloader
This repository contains a Python script that downloads your playlists or individual tracks from YouTube Music.<br>
Uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ytmusicapi](https://github.com/sigma67/ytmusicapi) libraries.

## Requirements
Make sure that you have ```ffmpeg```  installed.

```
pip install ffmpeg-python yt-dlp ytmusicapi
```

## How to use
```
-h, --help           Print this message
-a, --auth           Authorize (to be able to download your private playlists)
-l, --liked          Download all liked tracks
-p, --playlist ID    Download playlist by ID
-t, --track ID       Download single track by ID
--no-subfolders      Don't output tracks to folders named as album name
```

Example: ```python ytmd.py --track "https://music.youtube.com/watch?v=lYBUbBu4W08" --no-subfolders```
