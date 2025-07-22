import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
import random
import main_code as mc  # Your Spotify + VLC backend logic

# --- Globals ---
player = None
current_track_index = 0
tracks_to_swipe = []
right_swipes = []
song_genres_global = {}
album_photo = None
loading = False
current_bg_color = "#f0f0f0"  # Default light gray
current_button_color = "#000000"

preloaded_stream_urls = {}
preload_lock = threading.Lock()
PRELOAD_COUNT = 5  # How many upcoming tracks to preload

# --- Helper Functions ---

def get_dominant_color(image):
    try:
        img = image.copy()
        img.thumbnail((50, 50))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        pixels = list(img.getdata())
        avg_color = tuple(
            int(sum(channel) / len(pixels))
            for channel in zip(*pixels)
        )
        return '#%02x%02x%02x' % avg_color
    except Exception as e:
        print(f"Error getting dominant color: {e}")
        return "#f0f0f0"

def get_readable_text_color(bg_hex):
    try:
        r = int(bg_hex[1:3], 16) / 255.0
        g = int(bg_hex[3:5], 16) / 255.0
        b = int(bg_hex[5:7], 16) / 255.0
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        return "white" if luminance < 0.5 else "black"
    except:
        return "black"

def load_image_from_url(url, size=(300, 300)):
    try:
        response = requests.get(url, timeout=10)
        img = Image.open(BytesIO(response.content)).resize(size, Image.LANCZOS)
        return img, ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"Error loading image: {e}")
        return None, None

def darken_hex_color(hex_color, factor=0.5):
    # Remove leading '#'
    hex_color = hex_color.lstrip('#')

    # Parse R, G, B from hex
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    # Darken by factor
    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)

    # Clamp between 0 and 255
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    # Return as hex string
    return f"#{r:02x}{g:02x}{b:02x}"


def update_background_color(bg_color):
    global current_bg_color
    current_bg_color = bg_color
    text_color = get_readable_text_color(bg_color)
    current_button_color = darken_hex_color(current_bg_color)

    # Update root and frames backgrounds (you already do this)
    root.configure(bg=bg_color)
    for frame in (
        genre_frame, list_frame, button_frame,
        swipe_frame, header_frame, swipe_button_frame,
        album_art_frame
    ):
        frame.configure(bg=bg_color)

    # Update labels
    for widget in (name_label, artist_label, progress_label, status_label, album_art_label):
        widget.configure(bg=bg_color, fg=text_color)

    # Update listbox colors
    genre_listbox.configure(
        bg=bg_color,
        fg=text_color,
        selectbackground=current_button_color,
        selectforeground="white"
    )

    # **Dynamically update the ttk style for buttons:**
    style.configure(
        "Green.TButton",
        background=current_button_color,
        foreground="white"
    )
    style.map(
        "Green.TButton",
        background=[
            ("pressed", current_button_color),
            ("active", current_button_color),
            ("disabled", current_button_color),
            ("!active", current_button_color),
        ],
        foreground=[
            ("pressed", "white"),
            ("active", "white"),
            ("disabled", "white"),
            ("!active", "white"),
        ],
    )

    root.update_idletasks()


def stop_audio():
    global player
    if player:
        try:
            player.stop()
            player.release()
        except Exception as e:
            print(f"Error stopping audio: {e}")
        finally:
            player = None

def _track_query(track_dict):
    try:
        t = track_dict["track"]
        name = t["name"]
        artists = ", ".join(a["name"] for a in t["artists"])
        return f"{name} {artists}", name, artists
    except Exception as e:
        print(f"Error building track query: {e}")
        return "", "Unknown", "Unknown"

def preload_next_tracks(start_index):
    global preloaded_stream_urls
    for i in range(start_index, min(start_index + PRELOAD_COUNT, len(tracks_to_swipe))):
        with preload_lock:
            if i in preloaded_stream_urls:
                continue
        try:
            track_dict = tracks_to_swipe[i]
            query, _, _ = _track_query(track_dict)
            stream_url = mc.get_stream_url(query)
            with preload_lock:
                preloaded_stream_urls[i] = stream_url
            print(f"Preloaded track {i}: {query}")
        except Exception as e:
            print(f"Error preloading track {i}: {e}")

def update_ui_for_track(track_dict):
    global album_photo, current_bg_color, current_track_index, player
    _, track_name, artists = _track_query(track_dict)
    name_label.config(text=track_name)
    artist_label.config(text=artists)
    progress_label.config(text=f"{current_track_index + 1}/{len(tracks_to_swipe)}")

    album_art_label.config(image="", text="Loading...")
    root.update_idletasks()

    def _load_art_bg():
        global album_photo, current_bg_color
        try:
            images = track_dict["track"]["album"].get("images", [])
            img_url = images[0]["url"] if images else None
            if img_url:
                pil_img, tk_img = load_image_from_url(img_url)
                if pil_img and tk_img:
                    bg_color = get_dominant_color(pil_img)
                    current_bg_color = bg_color
                    def _apply():
                        album_art_label.config(image=tk_img, text="")
                        album_art_label.image = tk_img
                        update_background_color(bg_color)
                    root.after(0, _apply)
                    return
        except Exception as e:
            print(f"Error loading album art: {e}")

        def _fallback():
            album_art_label.config(image="", text="No Image")
            update_background_color("#f0f0f0")
        root.after(0, _fallback)

    threading.Thread(target=_load_art_bg, daemon=True).start()

    def _play_audio_bg():
        global player
        stop_audio()
        stream_url = None
        with preload_lock:
            stream_url = preloaded_stream_urls.pop(current_track_index, None)
        try:
            if not stream_url:
                query, _, _ = _track_query(track_dict)
                print(f"Fetching stream URL live for track {current_track_index}: {query}")
                stream_url = mc.get_stream_url(query)
            player = mc.instance.media_player_new()
            media = mc.instance.media_new(stream_url)
            player.set_media(media)
            player.play()
            print(f"Playing track {current_track_index}: {track_name} by {artists}")
            threading.Thread(target=preload_next_tracks, args=(current_track_index + 1,), daemon=True).start()
        except Exception as e:
            print(f"Error playing audio: {e}")

    threading.Thread(target=_play_audio_bg, daemon=True).start()

def show_next_track():
    global current_track_index
    if current_track_index >= len(tracks_to_swipe):
        stop_audio()
        messagebox.showinfo("Done", "No more songs to swipe!")
        return
    left_btn.config(state=tk.DISABLED)
    right_btn.config(state=tk.DISABLED)
    root.after(100, lambda: update_ui_for_track(tracks_to_swipe[current_track_index]))
    root.after(200, lambda: [left_btn.config(state=tk.NORMAL), right_btn.config(state=tk.NORMAL)])

def swipe_right():
    global current_track_index, right_swipes
    if current_track_index < len(tracks_to_swipe):
        right_swipes.append(tracks_to_swipe[current_track_index])
        current_track_index += 1
        show_next_track()

def swipe_left():
    global current_track_index
    if current_track_index < len(tracks_to_swipe):
        current_track_index += 1
        show_next_track()

def combine_tracks(selected_genres, song_genres):
    combined = []
    seen_ids = set()
    for genre in selected_genres:
        if genre in song_genres:
            for track in song_genres[genre]:
                tid = track["track"]["id"]
                if tid not in seen_ids:
                    combined.append(track)
                    seen_ids.add(tid)
        else:
            messagebox.showwarning("Warning", f"Genre '{genre}' not found.")
    random.shuffle(combined)
    return combined

def on_start_swiping():
    global tracks_to_swipe, current_track_index, right_swipes, loading, preloaded_stream_urls
    selected_indices = genre_listbox.curselection()
    if not selected_indices:
        messagebox.showinfo("Select Genre", "Please select at least one genre.")
        return
    loading = True
    start_button.config(state=tk.DISABLED, text="Loading...")
    status_label.config(text="Preparing your tracks...")
    root.update()
    selected_genres = [genre_listbox.get(i).split(" (")[0] for i in selected_indices]
    def process_tracks():
        global tracks_to_swipe, current_track_index, right_swipes, loading, preloaded_stream_urls
        combined_tracks = combine_tracks(selected_genres, song_genres_global)
        if not combined_tracks:
            messagebox.showinfo("No Songs", "No songs found for those genres.")
            loading = False
            start_button.config(state=tk.NORMAL, text="Start Swiping")
            status_label.config(text="")
            return
        tracks_to_swipe = combined_tracks
        current_track_index = 0
        right_swipes = []
        preloaded_stream_urls = {}
        genre_frame.pack_forget()
        swipe_frame.pack(fill="both", expand=True)
        show_next_track()
        loading = False
        start_button.config(state=tk.NORMAL, text="Start Swiping")
    threading.Thread(target=process_tracks, daemon=True).start()

def fetch_and_load_genres():
    global loading
    loading = True
    genre_listbox.delete(0, tk.END)
    status_label.config(text="Loading your music data...")
    start_button.config(state=tk.DISABLED, text="Loading...")
    root.update()
    try:
        liked_tracks = mc.get_all_liked_tracks(mc.sp)
        artist_ids = mc.get_artist_ids_from_tracks(liked_tracks)
        artist_genres = mc.get_artist_genres(mc.sp, artist_ids)
        global song_genres_global
        song_genres_global = mc.liked_songs_genre(liked_tracks, artist_genres)
        sorted_genres = sorted(song_genres_global.items(), key=lambda x: len(x[1]), reverse=True)
        for genre, tracks in sorted_genres:
            genre_listbox.insert(tk.END, f"{genre} ({len(tracks)})")
        status_label.config(text=f"Found {len(liked_tracks)} tracks across {len(sorted_genres)} genres")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load data: {str(e)}")
        status_label.config(text="Error loading data")
    finally:
        loading = False
        start_button.config(state=tk.NORMAL, text="Start Swiping")

def return_to_genres():
    stop_audio()
    swipe_frame.pack_forget()
    genre_frame.pack(fill="both", expand=True)

def create_playlist():
    if not right_swipes:
        messagebox.showinfo("No Songs", "You haven't swiped right on any songs yet!")
        return
    playlist_name = f"Music Tinder Selection - {len(right_swipes)} songs"
    track_uris = [track["track"]["uri"] for track in right_swipes]
    try:
        user_id = mc.sp.current_user()["id"]
        playlist = mc.sp.user_playlist_create(
            user=user_id,
            name=playlist_name,
            public=False,
            description="Songs you liked in Music Tinder"
        )
        for i in range(0, len(track_uris), 100):
            mc.sp.playlist_add_items(playlist["id"], track_uris[i:i+100])
        messagebox.showinfo("Success", f"Created playlist '{playlist_name}' with {len(track_uris)} songs!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create playlist: {str(e)}")

def on_close():
    stop_audio()
    root.destroy()

# ===================== GUI BUILD (REPLACEMENT) =====================
# Initialize main window
root = tk.Tk()
root.title("Music Tinder")
root.geometry("400x650")
root.protocol("WM_DELETE_WINDOW", on_close)
root.configure(bg=current_bg_color)

# Font definitions
title_font = tkfont.Font(family="Helvetica", size=18, weight="bold")
label_font = tkfont.Font(family="Helvetica", size=12)
button_font = tkfont.Font(family="Helvetica", size=12)

# --- ttk Style setup ---
style = ttk.Style()
try:
    style.theme_use('clam')
except tk.TclError:
    pass

# Green action button style (Tinder-like)
BTN_TEXT = "white"

style.configure(
    "Green.TButton",
    background=current_button_color,
    foreground=BTN_TEXT,
    borderwidth=0,
    focusthickness=0,
    focuscolor="",
    padding=(16, 10),   # roomy buttons
    relief="flat",
    font=button_font,
)
style.map(
    "Green.TButton",
    background=[
        ("pressed", current_button_color),
        ("active", current_button_color),
        ("disabled", current_button_color),
        ("!active", current_button_color),
    ],
    foreground=[
        ("pressed", BTN_TEXT),
        ("active", BTN_TEXT),
        ("disabled", BTN_TEXT),
        ("!active", BTN_TEXT),
    ],
    relief=[("pressed", "flat"), ("active", "flat"), ("!active", "flat")]
)
# Normalize layout so themes don't draw stray borders
style.layout("Green.TButton", [
    ("Button.border", {
        "sticky": "nswe", "children": [
            ("Button.padding", {
                "sticky": "nswe", "children": [
                    ("Button.label", {"sticky": "nswe"})
                ]
            })
        ]
    })
])

# ===================== GENRE SELECTION VIEW =====================
genre_frame = tk.Frame(root, padx=20, pady=20, bg=current_bg_color)
genre_frame.pack(fill="both", expand=True)

tk.Label(
    genre_frame, text="Music Tinder", font=title_font,
    bg=current_bg_color, fg=get_readable_text_color(current_bg_color)
).pack(pady=10)

tk.Label(
    genre_frame, text="Select genres to swipe:", font=label_font,
    bg=current_bg_color, fg=get_readable_text_color(current_bg_color)
).pack(pady=5)

list_frame = tk.Frame(genre_frame, bg=current_bg_color)
list_frame.pack(fill="both", expand=True)

scrollbar = ttk.Scrollbar(list_frame)
scrollbar.pack(side="right", fill="y")

genre_listbox = tk.Listbox(
    list_frame,
    selectmode=tk.MULTIPLE,
    width=40,
    height=15,
    yscrollcommand=scrollbar.set,
    font=label_font,
    bg=current_bg_color,
    fg=get_readable_text_color(current_bg_color),
    selectbackground=current_button_color,
    selectforeground="white",
    highlightthickness=0,
    borderwidth=0,
    relief="flat",
)
genre_listbox.pack(side="left", fill="both", expand=True)
scrollbar.config(command=genre_listbox.yview)

button_frame = tk.Frame(genre_frame, bg=current_bg_color)
button_frame.pack(pady=20)

start_button = ttk.Button(
    button_frame,
    text="Start Swiping",
    command=on_start_swiping,
    style="Green.TButton",
)
start_button.pack(pady=10)

status_label = tk.Label(
    genre_frame,
    text="",
    fg="gray",
    font=label_font,
    bg=current_bg_color,
)
status_label.pack()

# ===================== SWIPE VIEW (hidden until start) =====================
swipe_frame = tk.Frame(root, padx=20, pady=20, bg=current_bg_color)
# don't pack yet; shown later in on_start_swiping()

header_frame = tk.Frame(swipe_frame, bg=current_bg_color)
header_frame.pack(fill="x", pady=5)

back_button = ttk.Button(
    header_frame,
    text="👈 Back",
    command=return_to_genres,
    style="Green.TButton",
)
back_button.pack(side="left")

progress_label = tk.Label(
    header_frame,
    text="0/0",
    font=label_font,
    bg=current_bg_color,
    fg=get_readable_text_color(current_bg_color),
)
progress_label.pack(side="right")

album_art_frame = tk.Frame(
    swipe_frame,
    width=300,
    height=300,
    bg=current_bg_color,
    bd=2,
    relief="groove",
    highlightthickness=0,
)
album_art_frame.pack(pady=20)
album_art_frame.pack_propagate(False)

album_art_label = tk.Label(
    album_art_frame,
    text="No Image",
    font=label_font,
    bg=current_bg_color,
    fg=get_readable_text_color(current_bg_color),
)
album_art_label.pack(expand=True, fill="both")

name_label = tk.Label(
    swipe_frame,
    text="",
    font=tkfont.Font(size=16, weight="bold"),
    bg=current_bg_color,
    fg=get_readable_text_color(current_bg_color),
)
name_label.pack(pady=(10, 0))

artist_label = tk.Label(
    swipe_frame,
    text="",
    font=label_font,
    bg=current_bg_color,
    fg=get_readable_text_color(current_bg_color),
)
artist_label.pack(pady=(0, 15))

# Swipe buttons
swipe_button_frame = tk.Frame(swipe_frame, bg=current_bg_color)
swipe_button_frame.pack(pady=10)

left_btn = ttk.Button(
    swipe_button_frame,
    text="👎 Swipe Left",
    command=swipe_left,
    style="Green.TButton",
)
left_btn.pack(side="left", padx=10)

right_btn = ttk.Button(
    swipe_button_frame,
    text="👍 Swipe Right",
    command=swipe_right,
    style="Green.TButton",
)
right_btn.pack(side="left", padx=10)

# Playlist button
create_playlist_btn = ttk.Button(
    swipe_frame,
    text="🏁 Create Playlist from Likes",
    command=create_playlist,
    style="Green.TButton",
)
create_playlist_btn.pack(pady=20)
# ===================== END GUI BUILD =====================




# Load genres on startup
threading.Thread(target=fetch_and_load_genres, daemon=True).start()

root.mainloop()
