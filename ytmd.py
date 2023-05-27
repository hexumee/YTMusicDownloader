import ffmpeg
import json
import os
import re
import sys
import yt_dlp
from getopt import getopt
from mutagen.mp4 import MP4, MP4Cover
from mutagen.mp3 import MP3
from mutagen.id3 import APIC, TPE1, TIT2, TALB
from pathlib import Path
from ytmusicapi import YTMusic


HELP = "\n".join([
    "-h, --help           Print this message",
    "-a, --auth           Authorize (to be able to download your private playlists)",
    "-l, --liked          Download all liked tracks",
    "-p, --playlist ID    Download playlist by ID",
    "-t, --track ID       Download single track by ID",
    "--no-subfolders      Don't output tracks to folders named as album name"])
OPTIONS_LIST = ["help", "auth", "liked", "playlist=", "track=", "no-subfolders"]
ARGS_TEMPLATE = "halp:t:"
REGEX_RESTRICTED_TEMPLATE = r"[^\w().,&+\-\^%$;№@='\[\]{}`~# ]"

AUDIO_EXTENSION = "mp3"    # Can be mp3 or m4a
PLAYLIST_LIMIT = 100000    # Maximum amount of tracks being collected at once

UI_LANGUAGE = "en"         # While changing this, consider that you have:
                           # 1) added language to Accept-Language in authorize() function (check this: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Language)
                           # 2) made sure that ytmusicapi has this language in its locales folder
                           # 2.1) if there is no such folder, follow instructions (https://github.com/sigma67/ytmusicapi/blob/master/ytmusicapi/locales/README.rst)


def authorize():
    if os.path.exists("cookie.json"):
        print("\n".join(["[YTMD] cookie.json is here, so you can download your private playlists.",
                         "If you want to change cookie data, just remove cookie.json and re-run the script"]))
    else:
        print("\n".join(["[YTMD] Warning: cookie.json not found!",
                         "To get cookies data of music.youtube.com:",
                         "- in Chrome: Open DevTools => Application => Cookies",
                         "- in Firefox: Open DevTools => Storage => Cookies\n"]))
        
        cookie_sid = input("Provide SID value: ")
        if not cookie_sid:
            sys.exit("Empty value provided!")

        cookie_hsid = input("Provide HSID value: ")
        if not cookie_hsid:
            sys.exit("Empty value provided!")

        cookie_ssid = input("Provide SSID value: ")
        if not cookie_ssid:
            sys.exit("Empty value provided!")

        cookie_apisid = input("Provide APISID value: ")
        if not cookie_apisid:
            sys.exit("Empty value provided!")

        cookie_sapisid = input("Provide SAPISID value: ")
        if not cookie_sapisid:
            sys.exit("Empty value provided!")
            
        cookie_secure = input("Provide __Secure-3PAPISID value: ")
        if not cookie_secure:
            sys.exit("Empty value provided!")

        print("\n".join(["\n[YTMD] Now get a value of 'Authorization' field from any POST request.",
                         "To find an 'Authorization' field you need:",
                         "  1) Open a new tab",
                         "  2) Open DevTools => Network",
                         "  3) Go to music.youtube.com while DevTools are open",
                         "  4) Find a POST request to music.youtube.com and click on it",
                         "  5) Find a field named 'Authorization' and copy its value"]))
        
        auth_data = input("Provide 'Authorization' value: ")
        if not cookie_secure:
            sys.exit("Empty value provided!")

        cookie = "; ".join([
            "SID="+cookie_sid,
            "HSID="+cookie_hsid,
            "SSID="+cookie_ssid,
            "APISID="+cookie_apisid,
            "SAPISID="+cookie_sapisid,
            "__Secure-3PAPISID="+cookie_secure
        ])

        with open("cookie.json", "w") as f:
            json.dump({
                "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:108.0) Gecko/20100101 Firefox/108.0",
                "accept": "*/*",
                "accept-language": "en-US, ru-RU, en;q=0.75, ru;q=0.5",
                "authorization": auth_data,
                "content-type": "application/json",
                "x-goog-authuser": "0",
                "x-origin": "https://music.youtube.com",
                "cookie": cookie
            }, f)
        
        print("Saved! Now you can download your private playlists.")


def process_track(track_info, track_name):
    download_track(track_info['videoId'], track_name)

    # Compile absolute paths
    track_video = Path.cwd().absolute().joinpath(f"{track_name}.mp4").resolve()
    track_audio = Path.cwd().absolute().joinpath(f"{track_name}.{AUDIO_EXTENSION}").resolve()

    cover, _ = (
        ffmpeg
        .input(track_video)                                             # Path to downloaded MP4
        .filter('select', 'gte(n, 1)')                                  # Select the first frame of video stream
        .output('pipe:', vframes=1, format='image2', vcodec='mjpeg')    # Save it as JPEG to stdout (this will be track cover)
        .run(capture_stdout=True)
    )

    (
        ffmpeg
        .input(track_video)                                                      # Path to downloaded MP4
        .output(os.fspath(track_audio),                                          # Output audio stream
                format="ipod" if AUDIO_EXTENSION == "m4a" else "mp3",
                audio_bitrate=256000 if AUDIO_EXTENSION == "m4a" else 320000,
                vn=None)
        .run()
    )

    audio = MP4(track_audio) if AUDIO_EXTENSION == "m4a" else MP3(track_audio)

    if AUDIO_EXTENSION == "m4a":
        # Get track tags from track_info variable containing title, artists, album and etc. and save them to newly created audio file
        audio['covr'] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]
        audio['\xa9nam'] = track_info['title']

        if track_info['artists'] is not None:
            # Resulting string will look like this: Artist1, Artist2, Artist3
            # Even if originally it was Artist1, Artist2 & Artist3
            track_artists = ", ".join([track_info['artists'][i]['name'] for i in range(len(track_info['artists']))])
            audio['\xa9ART'] = track_artists

        if track_info['album'] is not None:
            audio['\xa9alb'] = track_info['album']['name']
    else:
        track_tags = audio.tags

        track_tags.add(APIC(encoding=3, mime='image/jpeg', type=3, data=cover))
        track_tags.add(TIT2(encoding=3, text=track_info['title']))

        if track_info['artists'] is not None:
            track_artists = ", ".join([track_info['artists'][i]['name'] for i in range(len(track_info['artists']))])
            track_tags.add(TPE1(encoding=3, text=track_artists))

        if track_info['album'] is not None:
            track_tags.add(TALB(encoding=3, text=track_info['album']['name']))
 
    audio.save()


def process_iter(track, no_subfolders=True):
    if track["videoId"] is not None:
        # Remove all characters from title that are not allowed in some filesystems and other ones
        file_path = re.sub(REGEX_RESTRICTED_TEMPLATE, '', track['title']).strip()
        
        # Same for the album name (track["album"] can be None if you download a track as video)
        if track["album"] is not None and not no_subfolders:
            file_path = os.path.join(re.sub(REGEX_RESTRICTED_TEMPLATE, '', track['album']['name']).strip(), file_path)
        
        # If track (or album with track inside) with the same name exists then just add "1" (or more) to the end (e.g. Already Here 1.mp3 or Already/Here 1.mp3)
        if not os.path.exists(f"{file_path}.{AUDIO_EXTENSION}"):
            process_track(track, file_path)
            os.remove(f"{file_path}.mp4")
        else:
            file_index = 1

            while os.path.exists(f"{file_path} {file_index}.{AUDIO_EXTENSION}"):
                file_index += 1
            else:
                # Download and set tags then remove original MP4
                process_track(track, f"{file_path} {file_index}")
                os.remove(f"{file_path} {file_index}.mp4")


def download_track(track_id, track_title=None):
    # If user provided a link (but you can provide just an ID)
    if track_id.startswith("https://"):
        track_id = track_id.split("v=")[1].split("&")[0]

    if track_title is None:
        track_title = track_id

    print(f"[YTMD] Starting: {track_title}")
    with yt_dlp.YoutubeDL({
        "format": "best",
        "outtmpl": f"{track_title}.%(ext)s"
    }) as ytdl:
        ytdl.download([f"https://www.youtube.com/watch?v={track_id}"])


def download_playlist(playlist_id, no_subfolders=False, download_liked=False):
    if not os.path.exists("cookie.json"):
        authorize()

    if not download_liked:
        if playlist_id.startswith("https://"):
            playlist_id = playlist_id.split("list=")[1]

        download_list = YTMusic("cookie.json", language=UI_LANGUAGE).get_playlist(playlist_id, PLAYLIST_LIMIT)
    else:
        download_list = YTMusic("cookie.json", language=UI_LANGUAGE).get_liked_songs(PLAYLIST_LIMIT)

    for track in download_list["tracks"]:
        process_iter(track, no_subfolders)


def download_single(track_id):
    if track_id.startswith("https://"):
        track_id = track_id.split("v=")[1].split("&")[0]

    # Get radio based on downloadable track (get_song() function doesn't return album name)
    track_info = YTMusic(language=UI_LANGUAGE).get_watch_playlist(videoId=track_id)['tracks'][0]

    process_iter(track_info, no_subfolders=True)


def ytmd(argv):
    args, vals = getopt(argv, ARGS_TEMPLATE, OPTIONS_LIST)

    if len(args) == 0:
        args = [("-h", "")]

    for arg, val in args:
        if arg in ("-h", "--help"):
            print(HELP)
        elif arg in ("-a", "--auth"):
            authorize()
        elif arg in ("-l", "--liked"):
            download_playlist(None, ("--no-subfolders" in argv), True)
        elif arg in ("-p", "--playlist"):
            download_playlist(val, ("--no-subfolders" in argv), False)
        elif arg in ("-t", "--track"):
            download_single(val)


if __name__ == "__main__":
    ytmd(sys.argv[1:])
