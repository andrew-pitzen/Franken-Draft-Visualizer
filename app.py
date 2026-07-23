import os
import re
import streamlit as st
import json
import zlib
import base64
from DraftConsol import DraftConsol

import secrets

@st.cache_resource
def draft_store():
    return {}

STORE = draft_store()


params = st.query_params

if "draft_loaded" not in st.session_state:
    st.session_state.draft_loaded = False

if "draft" in params and not st.session_state.draft_loaded:

    draft_id = params["draft"]

    if isinstance(draft_id, list):
        draft_id = draft_id[0]

    data = STORE.get(draft_id)

    if data is None:
        st.error("Draft not found.")
        st.stop()

    st.session_state.player_names = data["player_names"]
    st.session_state.master_lists = [
        DraftConsol(text)
        for text in data["texts"]
    ]
    st.session_state.player_hidden = [False] * len(data["player_names"])

    st.session_state.round_num = 0
    st.session_state.page = "viewer"
    st.session_state.draft_loaded = True

CARD_HEIGHT = 155


st.set_page_config(
    page_title="Draft Visualizer",
    layout="wide"
)

st.markdown("""
<style>

.block-container {
    padding-top: 1rem;
}

div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stImage"]) {
    padding-bottom: .25rem;
}

</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>

img {
    object-fit: contain;
}

div[data-testid="stImage"] img {
    max-height: 230px;
    object-fit: contain;
}

</style>
""", unsafe_allow_html=True)


st.markdown("""
<style>

div[data-testid="stImage"] img {
    max-height: 180px;
    object-fit: contain;
}

</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------
# Session State
# ----------------------------------------------------------

defaults = {
    "page": "home",
    "player_names": [],
    "master_lists": [],
    "player_hidden": [],
    "round_num": 0,

    "home_names": [""] * 6,
    "home_texts": [""] * 6,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

TALLY_KEY_ORDER = [
    "ABILITY",
    "TECH",
    "BREAKTHROUGH",
    "AGENT",
    "COMMANDER",
    "HERO",
    "MECH",
    "FLAGSHIP",
    "COMMODITIES",
    "PN",
    "HOMESYSTEM",
    "STARTINGTECH",
    "STARTINGFLEET",
    "BLUETILE",
    "REDTILE",
    "DRAFTORDER",
    "Additional Components:",
    "Replacement Components",
]

from pathlib import Path

ICON_ROOT = Path("imgs/Icons")

ICON_INDEX = {}

for file in ICON_ROOT.rglob("*"):
    if file.is_file() and file.suffix.lower() == ".png":
        ICON_INDEX[file.stem.lower()] = str(file)

IMG_ROOT = Path("imgs")

IMAGE_INDEX = {}

for file in IMG_ROOT.rglob("*"):
    if file.is_file() and file.suffix.lower() == ".png":
        key = str(file.relative_to(IMG_ROOT)).replace("\\", "/").lower()
        IMAGE_INDEX[key] = str(file)

st.sidebar.write("Images:", len(IMAGE_INDEX))
st.sidebar.write("Icons:", len(ICON_INDEX))

def find_image(relative_path):
    key = relative_path.lower()

    if key not in IMAGE_INDEX:
        st.sidebar.write("Missing:", key)

    return IMAGE_INDEX.get(key)

tile_check = re.compile(r"\((\d+)\)")
icon_pattern = re.compile(r":([^:]+):")

def image_path(key: str, value: str):

    lines = value.splitlines()

    first_line = lines[0] if lines else "None"
    second_line = lines[1] if len(lines) > 1 else ""

    first_line = (
        first_line
        .replace('"', "")
        .replace("?", "")
    )

    if key == "NO PICK":
        return None

    if key in ("REDTILE", "BLUETILE"):

        match = tile_check.search(lines[0])

        if match:
            return find_image(f"Tiles/ST_{match.group(1)}.png")

        return None

    if key == "COMMODITIES":
        return find_image(f"{key}/{second_line}.png")

    return find_image(f"{key}/{first_line}.png")

def replace_icons(text):

    def repl(match):

        name = match.group(1)

        path = f"imgs/Icons/{name}.png"

        if os.path.exists(path):
            return (
                f'<img src="{path}" '
                'style="height:20px;vertical-align:middle;">'
            )

        return match.group(0)

    return icon_pattern.sub(repl, text)


def render_pick(key, value):
    SWAP_KEYS = {
        "STARTINGFLEET",
    }

    card_image = image_path(key, value)

    lines = value.splitlines()

    name = lines[0] if lines else "Unknown"

    swap = key in SWAP_KEYS
    if not swap:
        st.markdown(
            f"<div style='text-align:center;font-weight:bold'>{key}</div>",
            unsafe_allow_html=True,
        )

        if card_image and os.path.exists(card_image):

            with open(card_image, "rb") as f:
                img_bytes = f.read()

            import base64

            encoded = base64.b64encode(img_bytes).decode()

            st.markdown(f"""
            <div style="
                height:{CARD_HEIGHT}px;
                display:flex;
                align-items:center;
                justify-content:center;
                margin-bottom:2px;
            ">
                <img src="data:image/png;base64,{encoded}"
                     style="
                         max-height:155px;
                         max-width:100%;
                         object-fit:contain;
                     ">
            </div>
            """, unsafe_allow_html=True)

        else:
            st.info("No image available")
    else:
        st.markdown(
            f"<div style='text-align:center;font-weight:bold'>{key}</div>",
            unsafe_allow_html=True,
        )

        display_lines = []

        for line in lines[1:]:
            lower = line.lower().strip()

            if lower.startswith("also adds:"):
                continue

            if lower.startswith("includes optional swaps:"):
                continue

            display_lines.append(line)

        html = convert_unit_lines(display_lines)

        # Replace icons
        parts = icon_pattern.split(html)
        rendered = ""

        for i, part in enumerate(parts):
            if i % 2 == 0:
                rendered += part
            else:
                icon_image = icon_path(part)
                if icon_image:
                    encoded = image_to_base64(icon_image)
                    rendered += (
                        f'<img src="data:image/png;base64,{encoded}" '
                        'style="height:25px;display:block;">'
                    )
                else:
                    rendered += f":{part}:"

        st.markdown(f"""
        <div style="
            height:{CARD_HEIGHT-20}px;
            display:flex;
            align-items:center;
            justify-content:center;
            margin-bottom:2px;
        ">
            <div style="
                display:flex;
                justify-content:center;
                align-items:center;
                alight-content:center;
                gap:2px;
                flex-wrap:wrap;
            ">
                {rendered}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
    # Card name
    st.markdown(
        f"<div style='text-align:center; font-weight:bold; "
        f"padding-top:4px;'>{name}</div>",
        unsafe_allow_html=True
    )
    extras = extract_extra_components(lines)

    from collections import defaultdict

    grouped_extras = defaultdict(list)

    for extra_key, extra_name in extras:
        grouped_extras[extra_key].append(extra_name)

    for extra_key, extra_names in grouped_extras.items():

        st.markdown(
            "<hr style='margin:6px 0 10px 0;'>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f"<div style='text-align:center;font-weight:bold'>{extra_key}</div>",
            unsafe_allow_html=True,
        )

        for extra_name in extra_names:

            parts = icon_pattern.split(extra_name)
            html = ""

            for i, part in enumerate(parts):
                if i % 2 == 0:
                    html += part
                else:
                    icon = icon_path(part)
                    if icon:
                        encoded = image_to_base64(icon)
                        html += (
                            f'<img src="data:image/png;base64,{encoded}" '
                            'style="height:20px;vertical-align:middle;margin:0 2px;">'
                        )
                    else:
                        html += f":{part}:"

            st.markdown(
                f"<div style='text-align:center;font-weight:bold'>{html}</div>",
                unsafe_allow_html=True,
            )

    # Details popover
    with st.popover("Details"):

        st.markdown(f"### {name}")

        if swap:
            if card_image and os.path.exists(card_image):
                st.image(card_image, use_container_width=True)
            else:
                st.info("No image available")
        else:
            for line in lines[1:]:

                lower = line.lower().strip()

                if lower.startswith("also adds:"):
                    continue

                if lower.startswith("includes optional swaps:"):
                    continue

                render_detail_line(line, key)

def render_description(text):

    parts = icon_pattern.split(text)

    for part_index, part in enumerate(parts):

        # Even indices are normal text
        if part_index % 2 == 0:

            if part.strip():
                st.write(part)

        # Odd indices are things inside colons
        else:

            image = f"imgs/Icons/{part}.png"

            if os.path.exists(image):
                st.image(image, width=32)

            else:
                st.write(f":{part}:")

def render_player(player_name, player_data):

    with st.container(border=True):

        st.markdown(
            f"<h3 style='margin:0 0 6px 0'>{player_name}</h3>",
            unsafe_allow_html=True,
        )

        items = list(player_data.items())

        for row in range(0, len(items), 3):

            row_items = items[row:row + 3]

            if len(row_items) == 3:
                render_cols = st.columns(3)

            elif len(row_items) == 2:
                c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
                render_cols = [c2, c3]

            else:
                c1, c2, c3 = st.columns([1, 2, 1])
                render_cols = [c2]

            for col, (key, value) in zip(render_cols, row_items):
                with col:
                    render_pick(key, value)

def clear_home_inputs():
    for i in range(6):
        st.session_state.home_names[i] = ""
        st.session_state.home_texts[i] = ""

        st.session_state[f"name_{i}"] = ""
        st.session_state[f"text_{i}"] = ""

def home_page():
    left, right = st.columns([1, 5])

    with left:
        if st.button("🗑 Clear"):
            clear_home_inputs()
            st.rerun()
    st.title("Draft Visualizer")

    st.write(
        "Paste each player's card-info channel."
    )

    with st.form("draft_input"):

        player_names = []
        master_lists = []

        for i in range(6):

            st.markdown(f"### Player {i+1}")

            name = st.text_input(
                "Name",
                key=f"name_{i}",
                value=st.session_state.home_names[i],
            )

            text = st.text_area(
                "Card Info",
                height=180,
                key=f"text_{i}",
                value=st.session_state.home_texts[i],
            )

            if text.strip():

                player_names.append(
                    name or f"Player {i+1}"
                )

                master_lists.append(
                    DraftConsol(text)
                )
                st.session_state.home_names[i] = name
                st.session_state.home_texts[i] = text

        submitted = st.form_submit_button(
            "Start Draft"
        )

    if submitted:

        if not master_lists:
            st.warning("Enter at least one player.")
            return

        data = {
            "player_names": player_names,
            "texts": [
                st.session_state.home_texts[i]
                for i in range(6)
                if st.session_state.home_texts[i].strip()
            ]
        }

        # Load into current session
        st.session_state.player_names = player_names
        st.session_state.master_lists = master_lists
        st.session_state.player_hidden = [False] * len(player_names)
        st.session_state.round_num = 0
        st.session_state.page = "viewer"

        # Update URL
        draft_id = secrets.token_urlsafe(6)

        STORE[draft_id] = data

        st.query_params.clear()
        st.query_params["draft"] = draft_id

        st.rerun()
def viewer_page():

    player_names = st.session_state.player_names
    master_lists = st.session_state.master_lists

    max_rounds = max(len(player) for player in master_lists)

    def prev_round():
        if max_rounds <= 1:
            return
        st.session_state.round_num = (
                                             st.session_state.round_num - 1
                                     ) % max_rounds
        st.session_state.round_selector = st.session_state.round_num

    def next_round():
        if max_rounds <= 1:
            return
        st.session_state.round_num = (
                                             st.session_state.round_num + 1
                                     ) % max_rounds
        st.session_state.round_selector = st.session_state.round_num

    def select_round():
        if max_rounds <= 1:
            st.session_state.round_num = 0
            return

        st.session_state.round_num = st.session_state.round_selector
    # --------------------
    # Sidebar
    # --------------------

    st.sidebar.title("Draft")

    if st.sidebar.button("🏠 Home"):
        st.session_state.page = "home"
        st.rerun()

    st.sidebar.divider()

    st.sidebar.subheader("Players")

    for i, name in enumerate(player_names):

        visible = st.sidebar.checkbox(
            name,
            value=not st.session_state.player_hidden[i],
            key=f"visible_{i}"
        )

        st.session_state.player_hidden[i] = not visible

    st.sidebar.divider()

    # ==================================================
    # Navigation goes HERE
    # ==================================================

    if "round_selector" not in st.session_state:
        st.session_state.round_selector = st.session_state.round_num

    single_round = max_rounds <= 1

    left, middle, right = st.columns([1, 2, 1])

    with left:
        st.button(
            "⬅ Previous",
            on_click=prev_round,
            disabled=single_round,
        )

    with middle:
        st.selectbox(
            "",
            options=list(range(max_rounds)),
            key="round_selector",
            format_func=lambda x: f"Round {x + 1}",
            label_visibility="collapsed",
            on_change=select_round,
            disabled=single_round,
        )

    with right:
        st.button(
            "Next ➡",
            on_click=next_round,
            disabled=single_round,
        )

    st.markdown(
        "<hr style='margin:6px 0 10px 0;'>",
        unsafe_allow_html=True,
    )
    round_num = st.session_state.round_num
    # ==================================================
    # Player Grid goes HERE
    # ==================================================

    # ===============================================
    # Main Layout
    # ===============================================

    viewer_col, tally_col = st.columns([3, 1], gap="large")

    with viewer_col:

        players = []

        for i, player in enumerate(master_lists):

            if st.session_state.player_hidden[i]:
                continue

            players.append(
                (
                    player_names[i],
                    player
                )
            )

        rows = [
            players[i:i + 2]
            for i in range(0, len(players), 2)
        ]

        for row in rows:

            cols = st.columns(2)

            for col, (name, player) in zip(cols, row):

                with col:

                    if round_num < len(player):
                        data = player[round_num]
                    else:
                        data = {"NO PICK": "None"}

                    render_player(name, data)

    with tally_col:

        build_tally(round_num)

def build_tally(round_num):

    st.header("Draft Tally")

    player_names = st.session_state.player_names
    master_lists = st.session_state.master_lists

    for player_name, player in zip(player_names, master_lists):

        with st.expander(player_name, expanded=True):

            grouped = {}

            # -----------------------------
            # Build grouped data
            # -----------------------------
            for r in range(round_num + 1):

                if r >= len(player):
                    continue

                for key, value in player[r].items():

                    lines = value.splitlines()
                    first = lines[0]

                    grouped.setdefault(key, []).append((r + 1, first))

                    for extra_key, extra_name in extract_extra_components(lines):

                        extra_name = re.sub(r":[^:\s]+:", "", extra_name)
                        extra_name = re.sub(r"\s+", " ", extra_name).strip()

                        grouped.setdefault(extra_key, []).append((r + 1, extra_name))

            all_keys = set()

            for rnd in player:
                all_keys.update(rnd.keys())

            for key in ("Replacement Component", "Additional Component"):
                if key in grouped:
                    all_keys.add(key)

            ordered = sorted(
                all_keys,
                key=lambda x: (
                    TALLY_KEY_ORDER.index(x)
                    if x in TALLY_KEY_ORDER
                    else len(TALLY_KEY_ORDER)
                )
            )

            # -----------------------------
            # Build sections
            # -----------------------------
            sections = []

            for key in ordered:

                total = sum(key in rnd for rnd in player)
                current = len(grouped.get(key, []))

                if key in ("Replacement Component", "Additional Component"):
                    heading = key
                else:
                    heading = f"{key} ({current}/{total})"

                entries = []

                for r, text in grouped.get(key, []):
                    entries.append((r, text, r == round_num + 1))

                sections.append({
                    "heading": heading,
                    "entries": entries,
                    "height": 1 + len(entries)
                })

            # -----------------------------
            # Balance columns
            # -----------------------------
            total_height = sum(section["height"] for section in sections)

            running_height = 0
            split_index = len(sections)

            for i, section in enumerate(sections):
                running_height += section["height"]

                if running_height >= total_height / 2:
                    split_index = i + 1
                    break

            left_sections = sections[:split_index]
            right_sections = sections[split_index:]

            # -----------------------------
            # Render helper
            # -----------------------------
            def render_sections(section_list):

                for section in section_list:

                    st.markdown(
                        f"""
                                 <div style="
                                     font-size:0.85rem;
                                     font-weight:600;
                                     margin-top:8px;
                                     margin-bottom:3px;
                                 ">
                                     {section['heading']}
                                 </div>
                                 """,
                        unsafe_allow_html=True,
                    )

                    for r, text, current in section["entries"]:
                        bg = "#00ad2a" if current else "transparent"

                        st.markdown(
                            f"""
                                     <div style="
                                         background:{bg};
                                         padding:1px 6px;
                                         margin:1px 0;
                                         border-radius:3px;
                                         line-height:1.05;
                                         font-size:0.75rem;
                                     ">
                                         <b>R{r}</b> • {text}
                                     </div>
                                     """,
                            unsafe_allow_html=True,
                        )

            left_col, right_col = st.columns(2, gap="small")

            with left_col:
                render_sections(left_sections)

            with right_col:
                render_sections(right_sections)

def render_detail_line(line, key):
    MULTILINE_KEYS = {
        "BLUETILE",
        "REDTILE",
        "HOMESYSTEM"
    }
    if key in MULTILINE_KEYS:
        line = line.replace(", ", "<br>")

    html = ""

    parts = icon_pattern.split(line)

    for i, part in enumerate(parts):

        if i % 2 == 0:
            html += part

        else:

            icon_image = icon_path(part)

            if icon_image:

                encoded = image_to_base64(icon_image)

                html += (
                    f'<img src="data:image/png;base64,{encoded}" '
                    'style="height:20px;'
                    'vertical-align:middle;'
                    'margin:0 2px;">'
                )

            else:
                html += f":{part}:"

    st.markdown(html, unsafe_allow_html=True)

import base64

def extract_extra_components(lines):
    extras = []

    for line in lines:
        lower = line.lower().strip()

        if lower.startswith("also adds:"):
            swaps = line.split(":", 1)[1].strip()

            for swap in swaps.split(","):
                swap = swap.strip()

                if not swap:
                    continue

                swap = re.sub(
                    r"^(Additional Component|Replacement Component):\s*",
                    "",
                    swap,
                    flags=re.IGNORECASE,
                )

                extras.append(("Replacement Component", swap))


        elif lower.startswith("includes optional swaps:"):

            swaps = line.split(":", 1)[1].strip()

            for swap in swaps.split(","):
                swap = swap.strip()

                if not swap:
                    continue

                swap = re.sub(
                    r"^(Additional Component|Replacement Component):\s*",
                    "",
                    swap,
                    flags=re.IGNORECASE,
                )

                extras.append(("Replacement Component", swap))

    return extras


def convert_unit_lines(lines):
    UNIT_MAP = {
        "fighter": "fighter",
        "fighters": "fighter",
        "infantry": "infantry",
        "space dock": "spacedock",
        "warsun": "warsun",
        "war sun": "warsun",
        "flagship": "flagship",
    }

    icons = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        m = re.match(r"(\d+)\s+(.+)", line, re.IGNORECASE)

        if not m:
            icons.append(line)
            continue

        count = int(m.group(1))
        unit = re.sub(r"\(.*?\)", "", m.group(2)).strip().lower()

        for key, icon in UNIT_MAP.items():
            if key in unit:
                icons.extend([f":{icon}:" for _ in range(count)])
                break
        else:
            icons.append(line)

    return " ".join(icons)


def image_to_base64(path):

    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def icon_path(token: str):
    return ICON_INDEX.get(token.strip().lower())

if st.session_state.page == "home":

    home_page()

else:

    viewer_page()

