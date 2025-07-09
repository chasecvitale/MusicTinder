import vlc
import yt_dlp
import time

# Fix VLC plugin path on macOS
vlc_plugin_path = "/Applications/VLC.app/Contents/MacOS/plugins"

# Create VLC instance with plugin path
instance = vlc.Instance('--plugin-path=' + vlc_plugin_path)

ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True}
ydl = yt_dlp.YoutubeDL(ydl_opts)

def get_stream_url(query):
    result = ydl.extract_info(f"ytsearch1:{query}", download=False)
    return result['entries'][0]['url']

def play_stream(stream_url):
    player = instance.media_player_new()
    media = instance.media_new(stream_url)
    player.set_media(media)
    player.play()
    return player

songs = ["Make You Mine, Madison Beer", "Hung Up, Madonna", "Reckless, Madison Beerp", "Black Barbies, Nicki Minaj", "Vogue, Madonna"]
urls=[]
urls.append(get_stream_url(songs[0]))

i = 0
while(True):

    player = play_stream(urls[i])
    urls.append(get_stream_url(songs[i+1]))
    input()
    player.stop()
    i+=1

# Wait so you can hear the audio
time.sleep(100)
player.stop()
