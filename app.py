import os
import re
import streamlit as st
import json
import zlib
import base64
from DraftConsol import DraftConsol
import html

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
    "summary_index": 0,
    "round_num": 0,
    "summary_selector": 0,
    "home_names": [""] * 6,
    "home_texts": [""] * 6,
    "tally_expanded": True,
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

SUMMARY_KEYS = [
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
    "TILES",
    "STARTINGTECH",
    "STARTINGFLEET",
    "DRAFTORDER",
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

FOLDER_TO_TYPE = {
    "ability": "ABILITY",
    "tech": "TECH",
    "breakthrough": "BREAKTHROUGH",
    "agent": "AGENT",
    "commander": "COMMANDER",
    "hero": "HERO",
    "mech": "MECH",
    "flagship": "FLAGSHIP",
    "pn": "PN",
}

NAME_TO_TYPE = {}

for rel_path in IMAGE_INDEX:
    parts = rel_path.split("/")

    if len(parts) < 2:
        continue

    folder = parts[0].lower()
    filename = Path(parts[-1]).stem.lower()

    draft_type = FOLDER_TO_TYPE.get(folder)

    if draft_type:
        NAME_TO_TYPE[filename] = draft_type


def infer_type_from_image(name: str):
    key = (
        name.replace('"', "")
            .replace("?", "")
            .strip()
            .lower()
    )

    return NAME_TO_TYPE.get(key)

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

def stat_bar(percent, color):
    st.markdown(
        f"""
        <div style="
            width:100%;
            height:16px;
            background:#e0e0e0;
            border-radius:8px;
            overflow:hidden;
        ">
            <div style="
                width:{percent * 100:.1f}%;
                height:100%;
                background:{color};
                border-radius:8px;
            "></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_pick(key, value, show_extras=True, show_key=True):

    SWAP_KEYS = {
        "STARTINGFLEET",
    }

    card_image = image_path(key, value)

    lines = value.splitlines()
    name = lines[0] if lines else "Unknown"

    description_lines = [
        line for line in lines[1:]
        if not line.lower().startswith((
            "also adds:",
            "includes optional swaps:"
        ))
    ]

    description = "\n".join(description_lines)

    tooltip = html.escape(
        re.sub(r":[^:\s]+:", "", description)
    )
    tooltip = re.sub(r"\s+", " ", tooltip).strip()

    swap = key in SWAP_KEYS

    # ---------------------------------------------------
    # Normal cards
    # ---------------------------------------------------
    if not swap:

        if show_key:
            st.markdown(
                f"<div style='text-align:center;font-weight:bold'>{key}</div>",
                unsafe_allow_html=True,
            )

        if card_image and os.path.exists(card_image):

            encoded = image_to_base64(card_image)

            st.markdown(f"""
            <div style="
                height:{CARD_HEIGHT}px;
                display:flex;
                align-items:center;
                justify-content:center;
                margin-bottom:2px;
            ">
                <img
                    src="data:image/png;base64,{encoded}"
                    alt="{tooltip}"
                    title="{tooltip}"
                    style="
                        max-height:155px;
                        max-width:100%;
                        object-fit:contain;
                    "
                >
            </div>
            """, unsafe_allow_html=True)

        else:
            st.info("No image available")

    # ---------------------------------------------------
    # Starting Fleet
    # ---------------------------------------------------
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

        icons = convert_unit_lines(display_lines)

        rendered = ""

        for icon_name, tooltip in icons:

            if icon_name is None:
                rendered += tooltip
                continue

            icon_image = icon_path(icon_name)

            if icon_image:

                encoded = image_to_base64(icon_image)

                rendered += (
                    f'<img '
                    f'src="data:image/png;base64,{encoded}" '
                    f'alt="{tooltip}" '
                    f'title="{tooltip}" '
                    f'style="height:25px;display:block;">'
                )

            else:
                rendered += tooltip

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
                gap:2px;
                flex-wrap:wrap;
            ">
                {rendered}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ---------------------------------------------------
    # Card name
    # ---------------------------------------------------

    st.markdown(
        f"<div style='text-align:center;font-weight:bold;padding-top:4px;'>"
        f"{name}"
        f"</div>",
        unsafe_allow_html=True,
    )

    if key == "STARTINGFLEET":
        value = starting_fleet_value(display_lines)

        st.markdown(
            f"""
            <div style="
                text-align:center;
                color:#666;
                font-size:0.9rem;
                margin-top:2px;
            ">
                Resource Value: <b>{value:g}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---------------------------------------------------
    # Extras
    # ---------------------------------------------------

    if show_extras:

        extras = extract_extra_components(lines)

        from collections import defaultdict

        grouped_extras = defaultdict(list)

        for extra_key, extra_name, draft_type in extras:
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

                tokens = re.findall(r":([^:]+):", extra_name)
                tooltip = html.escape(", ".join(tokens))

                parts = icon_pattern.split(extra_name)
                rendered_html = ""

                for i, part in enumerate(parts):

                    if i % 2 == 0:
                        rendered_html += part

                    else:

                        icon = icon_path(part)

                        if icon:

                            encoded = image_to_base64(icon)

                            rendered_html += (
                                f'<img '
                                f'src="data:image/png;base64,{encoded}" '
                                f'alt="{tooltip}" '
                                f'title="{tooltip}" '
                                'style="height:20px;vertical-align:middle;margin:0 2px;">'
                            )

                        else:
                            rendered_html += f":{part}:"

                st.markdown(
                    f"<div style='text-align:center;font-weight:bold'>{rendered_html}</div>",
                    unsafe_allow_html=True,
                )
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

def previous_summary():
    total = len(SUMMARY_KEYS)
    st.session_state.summary_index = (
        st.session_state.summary_index - 1
    ) % total


def next_summary():
    total = len(SUMMARY_KEYS)
    st.session_state.summary_index = (
        st.session_state.summary_index + 1
    ) % total


def select_summary():

    st.session_state.summary_index = (
        st.session_state.summary_selector
    )

def find_summary_picks(player, key):

    results = []
    seen = set()

    if key == "TILES":
        matching_keys = [
            "HOMESYSTEM",
            "BLUETILE",
            "REDTILE",
        ]
    else:
        matching_keys = [key]

    for rnd, draft_round in enumerate(player, start=1):

        #
        # Normal draft picks
        #
        for draft_key in matching_keys:

            if draft_key not in draft_round:
                continue

            results.append(
                (
                    rnd,
                    draft_key,
                    draft_round[draft_key],
                    None,
                )
            )

        #
        # Replacement / Additional Components
        #
        for _, value in draft_round.items():

            lines = value.splitlines()

            extras = extract_extra_components(lines)

            for extra_key, extra_name, draft_type in extras:

                if draft_type != key:
                    continue

                tokens = re.findall(r":([^:]+):", extra_name)

                if len(tokens) >= 2:
                    component_name = tokens[1]
                else:
                    component_name = re.sub(r":[^:]+:", "", extra_name).strip()

                value = component_name + "\n"

                identifier = (draft_type, component_name)

                if identifier not in seen:
                    seen.add(identifier)
                    results.append(
                        (
                            rnd,
                            draft_type,
                            value,
                            extra_key,
                        )
                    )

    return results

planet_values = re.compile(r"\((\d+)\s*/\s*(\d+)(?:/[^)]*)?\)")

def slice_totals(home_tiles):
    resources = 0
    influence = 0

    for _, _, value, _ in home_tiles:
        lines = value.splitlines()

        for line in lines[1:]:
            for match in planet_values.finditer(line):
                resources += int(match.group(1))
                influence += int(match.group(2))

    return resources, influence


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
def fake_sidebar(active_page):
    titles = {
        "home": "Draft",
        "viewer": "Rounds",
        "summary": "Summary",
    }

    st.title(titles.get(active_page, "Draft"))

    if st.button(
        "Home",
        disabled=active_page == "home",
        use_container_width=True,
    ):
        st.session_state.page = "home"
        st.rerun()

    if st.button(
        "Rounds",
        disabled=active_page == "viewer",
        use_container_width=True,
    ):
        st.session_state.page = "viewer"
        st.rerun()

    if st.button(
        "Summary",
        disabled=active_page == "summary",
        use_container_width=True,
    ):
        st.session_state.page = "summary"
        st.rerun()

    st.divider()

    if st.session_state.player_names:
        st.subheader("Players")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Show All", use_container_width=True):
                st.session_state.player_hidden = [False] * len(st.session_state.player_names)

                # Update checkbox widgets
                for i in range(len(st.session_state.player_names)):
                    st.session_state[f"sidebar_visible_{i}"] = True

                st.rerun()

        with col2:
            if st.button("Hide All", use_container_width=True):
                st.session_state.player_hidden = [True] * len(st.session_state.player_names)

                # Update checkbox widgets
                for i in range(len(st.session_state.player_names)):
                    st.session_state[f"sidebar_visible_{i}"] = False

                st.rerun()
        st.divider()
        for i, name in enumerate(st.session_state.player_names):

            key = f"sidebar_visible_{i}"

            # Initialize once
            if key not in st.session_state:
                st.session_state[key] = not st.session_state.player_hidden[i]

            st.checkbox(
                name,
                key=key,
            )

            st.session_state.player_hidden[i] = not st.session_state[key]
def home_page():
    sidebar, content = st.columns([1,5], gap="large")
    with sidebar:
        fake_sidebar("home")
    with content:
        top_left, _ = st.columns([1, 5])
        with top_left:
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
    sidebar, content = st.columns([1, 5], gap="large")

    max_rounds = max(len(player) for player in master_lists)
    single_round = max_rounds <= 1  # Moved up so callbacks can access it

    # 1. Centralize the state update for all navigation changes
    def update_round_state(new_round):
        st.session_state.round_num = new_round
        # Update both widget keys so they stay visually synced
        st.session_state.selector_top = new_round
        st.session_state.selector_bottom = new_round

    def prev_round():
        if not single_round:
            update_round_state((st.session_state.round_num - 1) % max_rounds)

    def next_round():
        if not single_round:
            update_round_state((st.session_state.round_num + 1) % max_rounds)

    # 2. Callback for when either selectbox changes
    def sync_selector(location):
        selected_val = st.session_state[f"selector_{location}"]
        update_round_state(selected_val)

    def round_navigation(location):
        left, middle, right = st.columns([1, 2, 1])

        with left:
            st.button(
                "⬅ Previous",
                key=f"prev_{location}",
                on_click=prev_round,
                disabled=single_round,
            )

        with middle:
            # Initialize the session state for this widget if it doesn't exist
            if f"selector_{location}" not in st.session_state:
                st.session_state[f"selector_{location}"] = st.session_state.round_num

            st.selectbox(
                "",
                options=range(max_rounds),
                format_func=lambda r: f"Round {r + 1}",
                key=f"selector_{location}",
                label_visibility="collapsed",
                disabled=single_round,
                on_change=sync_selector,  # Fire callback before rerun
                kwargs={"location": location}  # Pass which selector triggered it
            )

        with right:
            st.button(
                "Next ➡",
                key=f"next_{location}",
                on_click=next_round,
                disabled=single_round,
            )

        st.divider()

    with sidebar:
        fake_sidebar("viewer")

    # ===============================================
    # Main Layout
    # ===============================================
    round_num = st.session_state.round_num
    with content:

        round_navigation("top")

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
        round_navigation("bottom")

def build_tally(round_num, show_title=True, players_per_row=None):
    if "tally_expanded" not in st.session_state:
        st.session_state.tally_expanded = True

    if show_title:
        # Create columns so the button sits right next to the header
        title_col, btn_col = st.columns([2, 1])
        with title_col:
            st.header("Draft Tally")
        with btn_col:
            # Dynamic label based on current state
            btn_label = "Collapse All" if st.session_state.tally_expanded else "Expand All"
            if st.button(btn_label, key="toggle_tally_all", use_container_width=True):
                st.session_state.tally_expanded = not st.session_state.tally_expanded
                st.rerun()

    player_names = st.session_state.player_names
    master_lists = st.session_state.master_lists
    visible_players = [
        (name, player)
        for i, (name, player) in enumerate(zip(player_names, master_lists))
        if not st.session_state.player_hidden[i]
    ]
    if players_per_row is None:
        rows = [[player] for player in visible_players]
    else:
        rows = [
            visible_players[i:i + players_per_row]
            for i in range(0, len(visible_players), players_per_row)
        ]
    for row in rows:
        cols = st.columns(len(row), gap="large")
        for col, (player_name, player) in zip(cols, row):
            with col:
                # Use session state here to expand or collapse all
                with st.expander(player_name, expanded=st.session_state.tally_expanded):
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
                            for extra_key, extra_name, draft_type in extract_extra_components(lines):
                                display_name = re.sub(r":[^:]+:", "", extra_name).strip()
                                if draft_type:
                                    display_name = f"{display_name} - {draft_type}"
                                grouped.setdefault(extra_key, []).append(
                                    (r + 1, display_name)
                                )
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
                    sections = []
                    for key in ordered:
                        total = sum(key in rnd for rnd in player)
                        current = len(grouped.get(key, []))
                        if key in ("Replacement Component", "Additional Component"):
                            heading = key
                        else:
                            heading = f"{key} ({current}/{total})"
                        entries = [
                            (r, text, r == round_num + 1)
                            for r, text in grouped.get(key, [])
                        ]
                        sections.append({
                            "heading": heading,
                            "entries": entries,
                            "height": 1 + len(entries),
                        })
                    total_height = sum(s["height"] for s in sections)
                    running = 0
                    split = len(sections)
                    for i, section in enumerate(sections):
                        running += section["height"]
                        if running >= total_height / 2:
                            split = i + 1
                            break
                    left_sections = sections[:split]
                    right_sections = sections[split:]

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

def build_summary():
    player_names = st.session_state.player_names
    master_lists = st.session_state.master_lists
    grouped = {}
    # --------------------------------------------
    # Gather every pick by key, then by player
    # --------------------------------------------
    for i, (player_name, player) in enumerate(zip(player_names, master_lists)):
        if st.session_state.player_hidden[i]:
            continue
        for rnd, draft_round in enumerate(player, start=1):
            for key, value in draft_round.items():
                lines = value.splitlines()
                name = lines[0] if lines else ""
                grouped.setdefault(key, {})
                grouped[key].setdefault(player_name, [])
                grouped[key][player_name].append(
                    (rnd, name)
                )
                # Include replacement/additional components
                for extra_key, extra_name, draft_type in extract_extra_components(lines):
                    extra_name = re.sub(r":[^:\s]+:", "", extra_name)
                    extra_name = re.sub(r"\s+", " ", extra_name).strip()
                    grouped.setdefault(extra_key, {})
                    grouped[extra_key].setdefault(player_name, [])
                    grouped[extra_key][player_name].append(
                        (rnd, extra_name)
                    )
    # --------------------------------------------
    # Order keys
    # --------------------------------------------
    ordered_keys = sorted(
        grouped.keys(),
        key=lambda x: (
            TALLY_KEY_ORDER.index(x)
            if x in TALLY_KEY_ORDER
            else len(TALLY_KEY_ORDER)
        )
    )

    # --------------------------------------------
    # Display
    # --------------------------------------------
    visible_players = [
        name
        for i, name in enumerate(st.session_state.player_names)
        if not st.session_state.player_hidden[i]
    ]

    for key in ordered_keys:

        total = sum(
            len(entries)
            for entries in grouped[key].values()
        )

        with st.expander(f"{key} ({total})", expanded=True):

            cols = st.columns(len(visible_players))

            for col, player_name in zip(cols, visible_players):

                with col:

                    st.markdown(f"#### {player_name}")

                    for rnd, item in grouped[key].get(player_name, []):
                        st.markdown(
                            f"**R{rnd}** • {item}"
                        )


def render_detail_line(line, key):
    MULTILINE_KEYS = {
        "BLUETILE",
        "REDTILE",
        "HOMESYSTEM"
    }
    if key in MULTILINE_KEYS:
        line = line.replace(", ", "<br>")

    rendered_html = ""

    parts = icon_pattern.split(line)

    for i, part in enumerate(parts):

        if i % 2 == 0:
            rendered_html += part

        else:

            icon_image = icon_path(part)

            if icon_image:

                encoded = image_to_base64(icon_image)

                rendered_html += (
                    f'<img src="data:image/png;base64,{encoded}" '
                    'style="height:20px;'
                    'vertical-align:middle;'
                    'margin:0 2px;">'
                )

            else:
                rendered_html += f":{part}:"

    st.markdown(rendered_html, unsafe_allow_html=True)

import base64

def extract_extra_components(lines):
    extras = []

    TYPE_MAP = {
        "agent": "AGENT",
        "commander": "COMMANDER",
        "hero": "HERO",
        "mech": "MECH",
        "flagship": "FLAGSHIP",
        "tech": "TECH",
        "pn": "PN",
        "ability": "ABILITY",
        "breakthrough": "BREAKTHROUGH",
    }

    for line in lines:
        lower = line.lower().strip()

        if lower.startswith("also adds:"):
            category = "Additional Component"
            swaps = line.split(":", 1)[1].strip()

        elif lower.startswith("includes optional swaps:"):
            category = "Replacement Component"
            swaps = line.split(":", 1)[1].strip()

        else:
            continue

        for swap in swaps.split(","):
            swap = swap.strip()
            if not swap:
                continue

            tokens = re.findall(r":([^:]+):", swap)

            draft_type = None

            for token in tokens:
                token_lower = token.lower()

                for key, value in TYPE_MAP.items():
                    if token_lower.endswith(key):
                        draft_type = value
                        break

                if draft_type:
                    break

            if draft_type is None:
                plain_name = re.sub(r":[^:]+:", "", swap).strip()
                draft_type = infer_type_from_image(plain_name)

            if draft_type is None:
                draft_type = "ABILITY"

            extras.append((category, swap, draft_type))

    return extras


def convert_unit_lines(lines):
    """
        Returns [(icon_name, tooltip), ...]
        Handles:
            1 fighter, 2 destroyers
            multiple lines
            :fighter::destroyer::destroyer:
        """

    UNIT_MAP = {
        "fighter": "fighter",
        "fighters": "fighter",
        "destroyer": "destroyer",
        "destroyers": "destroyer",
        "carrier": "carrier",
        "carriers": "carrier",
        "cruiser": "cruiser",
        "cruisers": "cruiser",
        "dreadnought": "dreadnought",
        "dreadnoughts": "dreadnought",
        "infantry": "infantry",
        "space dock": "spacedock",
        "spacedock": "spacedock",
        "war sun": "warsun",
        "warsun": "warsun",
        "flagship": "flagship",
    }

    tooltip = html.escape(", ".join(
        l.strip() for l in lines if l.strip()
    ))

    icons = []

    #
    # Flatten into comma-separated pieces.
    #
    parts = []

    for line in lines:
        parts.extend(x.strip() for x in line.split(",") if x.strip())

    for part in parts:

        #
        # Case 3
        #
        if ":" in part:
            for token in re.findall(r":([^:]+):", part):
                icons.append((token.lower(), tooltip))
            continue

        #
        # Case 1 / Case 2
        #
        m = re.match(r"(\d+)\s+(.+)", part, re.I)

        if not m:
            continue

        count = int(m.group(1))
        unit = re.sub(r"\(.*?\)", "", m.group(2)).strip().lower()

        for key, icon in UNIT_MAP.items():
            if key == unit:
                icons.extend([(icon, tooltip)] * count)
                break

    return icons

UNIT_VALUES = {
    "warsun": 12,
    "cruiser": 2,
    "carrier": 3,
    "dreadnought": 4,
    "destroyer": 1,
    "fighter": 0.5,
    "infantry": 0.5,
    "pds": 3,
    "spacedock": 3,
    "mech": 2,
}

def starting_fleet_value(lines):
    """
    Returns the total resource value of a starting fleet.
    Works with both:
        2 infantry, 1 carrier
    and
        :infantry::infantry::carrier:
    """

    total = 0

    for icon_name, _ in convert_unit_lines(lines):
        total += UNIT_VALUES.get(icon_name.lower(), 0)

    return total

def summary_page():

    if not st.session_state.master_lists:
        st.warning("No draft loaded.")
        return
    sidebar, content = st.columns([1, 5], gap="large")

    # 1. Centralize the state update for summary navigation
    def update_summary_state(new_index):
        st.session_state.summary_index = new_index
        # Keep both top and bottom selectors visually synced
        st.session_state.summary_selector_top = new_index
        st.session_state.summary_selector_bottom = new_index

    def prev_summary_callback():
        total = len(SUMMARY_KEYS)
        update_summary_state((st.session_state.summary_index - 1) % total)

    def next_summary_callback():
        total = len(SUMMARY_KEYS)
        update_summary_state((st.session_state.summary_index + 1) % total)

    # 2. Callback for when either selectbox changes
    def sync_summary_selector(location):
        selected_val = st.session_state[f"summary_selector_{location}"]
        update_summary_state(selected_val)

    with sidebar:
        fake_sidebar("summary")

    #
    # Player visibility
    #
    st.sidebar.divider()

    # 3. Add the 'location' parameter to the function definition
    def summary_navigation(location):

        left, middle, right = st.columns([1, 2, 1])

        with left:
            st.button(
                "⬅ Previous",
                on_click=prev_summary_callback,
                key=f"summary_prev_{location}", # Ensure unique button keys
            )

        with middle:
            if f"summary_selector_{location}" not in st.session_state:
                st.session_state[f"summary_selector_{location}"] = st.session_state.summary_index

            st.selectbox(
                "",
                options=range(len(SUMMARY_KEYS)),
                format_func=lambda i: SUMMARY_KEYS[i],
                key=f"summary_selector_{location}",
                label_visibility="collapsed",
                on_change=sync_summary_selector,  # Fire callback before rerun
                kwargs={"location": location}     # Pass which selector triggered it
            )

        with right:
            st.button(
                "Next ➡",
                on_click=next_summary_callback,
                key=f"summary_next_{location}", # Ensure unique button keys
            )

        st.divider()

    with content:
        summary_navigation("top")
        current_key = SUMMARY_KEYS[st.session_state.summary_index]

        #
        # Player cards
        #

        players = []

        for i, player in enumerate(st.session_state.master_lists):

            if st.session_state.player_hidden[i]:
                continue

            players.append(
                (
                    st.session_state.player_names[i],
                    player
                )
            )
        # -------------------------------------------------
        # Resource totals for proportional bars
        # -------------------------------------------------

        resource_totals = {}
        influence_totals = {}

        if current_key == "TILES":

            for player_name, player in players:
                results = find_summary_picks(player, "TILES")

                other_tiles = [
                    r for r in results
                    if r[1] != "HOMESYSTEM"
                ]

                resources, influence = slice_totals(other_tiles)

                resource_totals[player_name] = resources
                influence_totals[player_name] = influence

                max_resources = max(resource_totals.values(), default=1)
                max_influence = max(influence_totals.values(), default=1)


        rows = [
            players[i:i+2]
            for i in range(0, len(players), 2)
        ]

        for row in rows:

            cols = st.columns(2)

            for col, (player_name, player) in zip(cols, row):

                with col:

                    with st.container(border=True):

                        st.markdown(f"### {player_name}")

                        results = find_summary_picks(player, current_key)

                        if not results:
                            st.info("No Pick")
                            continue

                        if current_key == "TILES":
                            home_tiles = [r for r in results if r[1] == "HOMESYSTEM"]
                            other_tiles = [r for r in results if r[1] != "HOMESYSTEM"]
                            groups = [home_tiles, other_tiles]
                        else:
                            groups = [results]

                        for group_index, group in enumerate(groups):

                            if not group:
                                continue

                            # Divider before non-home-system tiles
                            if group_index:
                                st.markdown(
                                    "<hr style='margin:10px 0;'>",
                                    unsafe_allow_html=True,
                                )


                            for start in range(0, len(group), 3):

                                chunk = group[start:start + 3]

                                if len(chunk) == 3:
                                    render_cols = st.columns(3)
                                elif len(chunk) == 2:
                                    c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
                                    render_cols = [c2, c3]
                                else:
                                    c1, c2, c3 = st.columns([1, 2, 1])
                                    render_cols = [c2]

                                for render_col, (rnd, key, value, component_type) in zip(render_cols, chunk):
                                    with render_col:

                                        render_pick(
                                            key,
                                            value,
                                            show_extras=False,
                                            show_key=False,
                                        )

                                        if component_type:
                                            st.markdown(
                                                f"""
                                                    <div style="
                                                        text-align:center;
                                                        color:#777;
                                                        font-size:0.8rem;
                                                        margin-top:2px;
                                                    ">
                                                        {component_type}
                                                    </div>
                                                                    """,
                                                unsafe_allow_html=True,
                                            )

                                        st.markdown(
                                            f"""
                                                <div style="
                                                    text-align:center;
                                                    color:gray;
                                                    margin-top:4px;
                                                ">
                                                    Round {rnd}
                                                </div>
                                                """,
                                            unsafe_allow_html=True,
                                        )
                        #
                        # Resource / Influence bars
                        #
                        if current_key == "TILES":
                            resources = resource_totals[player_name]
                            influence = influence_totals[player_name]

                            resource_percent = (
                                resources / max_resources
                                if max_resources else 0
                            )

                            influence_percent = (
                                influence / max_influence
                                if max_influence else 0
                            )

                            left, right = st.columns(2)

                            with left:
                                st.markdown(
                                    f"<div style='text-align:center;font-size:0.9rem;'>"
                                    f"Resources <b>{resources}</b></div>",
                                    unsafe_allow_html=True,
                                )
                                stat_bar(resource_percent, "#d4af37")  # gold

                            with right:
                                st.markdown(
                                    f"<div style='text-align:center;font-size:0.9rem;'>"
                                    f"Influence <b>{influence}</b></div>",
                                    unsafe_allow_html=True,
                                )
                                stat_bar(influence_percent, "#4a90e2")  # blue

                            st.markdown("<div style='height:8px'></div>",
                                        unsafe_allow_html=True)
        summary_navigation("bottom")

def image_to_base64(path):

    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def icon_path(token: str):
    return ICON_INDEX.get(token.strip().lower())

if st.session_state.page == "home":
    home_page()

elif st.session_state.page == "viewer":
    viewer_page()

elif st.session_state.page == "summary":
    summary_page()

else:
    # Fallback
    st.session_state.page = "home"
    st.rerun()

