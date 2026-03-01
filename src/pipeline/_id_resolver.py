# src/pipeline/_id_resolver.py

import json
import tkinter as tk

from tkinter import ttk, messagebox
from pathlib import Path
from typing import Dict
from hashlib import sha256

from src.constants import FileNames

#-------------------------------------------------------------------------

def load_id_map(input_path: str) -> Dict[str, str]:
    """
    Load player_id_map.json from input path.
    Returns an empty map structure if the file does not exist yet.

    Parameters:
    -----------
    input_path: str
        path to the input folder containing player_id_map.json

    Returns:
    --------
    Dict[str, str]:
        flat dict mapping player names to player ids
    """
    path = Path(input_path) / FileNames.Input.PLAYER_ID_MAP
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)
    

def save_id_map(id_map: Dict[str, str], input_path: str) -> None:
    """
    Write the updated player_id_map.json back to input_path.
    
    Parameters:
    -----------
    id_map: Dict[str, str]
        flat dict mapping player names to canonical ids
    input_path: str
        path to the input folder containing player_id_map.json
    """
    path = Path(input_path) / FileNames.Input.PLAYER_ID_MAP
    Path(input_path).mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(id_map, f, indent=2, ensure_ascii=False)

#-------------------------------------------------------------------------

def load_players(input_path: str) -> Dict[str, Dict]:
    """
    Load players.json from input path.
    Returns an empty dict if the file does not exist yet.
    
    Parameters:
    -----------
    input_path: str
        path to the input folder containing players.json
        
    Returns:
    --------
    Dict[str, Dict]:
        dict mapping player ids to player records
    """
    path = Path(input_path) / FileNames.Input.PLAYERS
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)
    

def save_players(players: Dict[str, Dict], input_path: str) -> None:
    """
    Write the updated players.json back to input_path.
    
    Parameters:
    -----------
    players: Dict[str, Dict]
        dict mapping player ids to player records
    input_path: str
        path to the input folder containing players.json
    """
    path = Path(input_path) / FileNames.Input.PLAYERS
    Path(input_path).mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)

#-------------------------------------------------------------------------

def _generate_canonical_id(name: str, players: Dict[str, Dict]) -> str:
    """
    Generate the next sequential canonical player id.
    Derives the next number from existing canconical ids in players.json.
    The id format is "PLR-XXX-EXT" where XXX is a zero-padded sequential number and EXT is a short hash of the name to avoid collisions.

    Parameters:
    -----------
    name: str
        the player name for which we want to generate a canonical id
    players: Dict[str, Dict]
        flat dict mapping canconical_id to player record

    Returns:
    --------
    str:
        new canonical_id string in the format "PLR-XXX-EXT" where XXX is a zero-padded sequential number.
    """
    numbers = [
        int(pid.split("-")[1])
        for pid in players.keys()
        if pid.startswith("PLR-")
        and pid.split("-")[1].isdigit()
    ]
    next_number = max(numbers, default=0) + 1
    extension = sha256(name.encode()).hexdigest()[:6].upper()
    return f"PLR-{next_number:03d}-{extension}"

#-------------------------------------------------------------------------

def resolve_player(scraped_name: str, id_map: Dict[str, str], players: Dict[str, Dict], input_path: str) -> str:
    """
    Resolve a scraped player name to a canonical ID.
    First attempts an automatic lookup by name in the id_map.
    If not found, opens an interactive popup for manual resolution.
    Presists any new resolutions to both files immediately.

    Parameters:
    -----------
    scraped_name: str
        player name as scraped from the raw file
    id_map: Dict[str, str]
        flat dict mapping scraped player names to canonical ids
    players: Dict[str, Dict]
        dict mapping canonical player ids to player records
    input_path: str
        path to the input folder containing players.json and player_id_map.json

    Returns:
    --------
    str:
        canonical player id corresponding to the scraped name
    """
    if scraped_name in id_map:
        return id_map[scraped_name]
    
    canonical_id = _open_resolution_popup(scraped_name, id_map, players)

    if canonical_id == "unknown":
        raise ValueError(f"Player name '{scraped_name}' could not be resolved. Please resolve this player manually and re-run consolidation.")

    id_map[scraped_name] = canonical_id
    save_id_map(id_map, input_path)
    save_players(players, input_path)

    return canonical_id

#-------------------------------------------------------------------------

def _open_resolution_popup(scraped_name: str, id_map: Dict[str, str], players: Dict[str, Dict]) -> str:
    """
    Open a tkinter popup to manually resolve an unknown player name.
    Offers two actions:
        - Link to an existing player (searchable list with autofill)
        - Register as a new player (auto-generates canconical ID, creates skeleton record)

    Parameters:
    -----------
    scraped_name: str
        the unknown player name to resolve
    id_map: Dict[str, str]
        flat dict mapping scraped player names to canonical ids
    players: Dict[str, Dict]
        dict mapping canonical player ids to player records

    Returns:
    --------
    str:
        the resolved canonical player id
    """
    result = {"canonical_id": "unknown"}

    root = tk.Tk()
    root.title("Unknown Player")
    root.resizable(False, False)
    root.configure(bg="#1e1e2e")

    # ── Styling ───────────────────────────────
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TFrame", background="#1e1e2e")
    style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Courier New", 11))
    style.configure("Header.TLabel", background="#1e1e2e", foreground="#cba6f7", font=("Courier New", 13, "bold"))
    style.configure("Muted.TLabel", background="#1e1e2e", foreground="#6c7086", font=("Courier New", 10))
    style.configure("TButton", font=("Courier New", 10), padding=6)
    style.configure("Accent.TButton", background="#cba6f7", foreground="#1e1e2e")
    style.configure("TEntry", fieldbackground="#313244", foreground="#cdd6f4", font=("Courier New", 11))
    style.configure("Treeview", background="#313244", foreground="#cdd6f4", fieldbackground="#313244", font=("Courier New", 10), rowheight=28)
    style.configure("Treeview.Heading", background="#45475a", foreground="#cdd6f4", font=("Courier New", 10, "bold"))
    style.map("Treeview", background=[("selected", "#cba6f7")], foreground=[("selected", "#1e1e2e")])

    # ── Layout ───────────────────────────────
    outer = ttk.Frame(root, padding=20)
    outer.pack(fill="both", expand=True)

    ttk.Label(outer, text="⚠  Unknown Player Encountered", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
    ttk.Label(outer, text=f"Scraped name:  {scraped_name}").pack(anchor="w")
    ttk.Label(outer, text="Link to an existing player or register as new.", style="Muted.TLabel").pack(anchor="w", pady=(2, 16))

    # Search
    ttk.Label(outer, text="Search existing players:").pack(anchor="w")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(outer, textvariable=search_var, width=48)
    search_entry.pack(fill="x", pady=(4, 8))
    search_entry.focus()

    # Results tree
    tree_frame = ttk.Frame(outer)
    tree_frame.pack(fill="both", expand=True)
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
    tree = ttk.Treeview(
        tree_frame,
        columns=("id", "name"),
        show="headings",
        height=8,
        yscrollcommand=scrollbar.set
    )
    scrollbar.config(command=tree.yview)
    tree.heading("id", text="Canonical ID")
    tree.heading("name", text="Display Name")
    tree.column("id", width=110, anchor="center")
    tree.column("name", width=280)
    scrollbar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)

    # Build display list from players.json records
    all_players = [
        (record["canonical_id"], record["display_name"])
        for record in players.values()
    ]

    def _refresh_tree(query: str = "") -> None:
        tree.delete(*tree.get_children())
        q = query.strip().lower()
        for pid, display_name in sorted(all_players, key=lambda x: x[1]):
            if q in display_name.lower() or q in pid.lower():
                tree.insert("", "end", values=(pid, display_name))

    def _on_search_changed(*_) -> None:
        _refresh_tree(search_var.get())

    search_var.trace_add("write", _on_search_changed)

    # Autofill search with scraped name on open
    search_var.set(scraped_name)
    search_entry.icursor("end")

    # ── Action buttons ────────────────────────
    btn_frame = ttk.Frame(outer)
    btn_frame.pack(fill="x", pady=(12, 0))

    def _link_selected() -> None:
        selected = tree.focus()
        if not selected:
            messagebox.showwarning(
                "No selection",
                "Please select a player from the list to link to.",
                parent=root
            )
            return
        canonical_id = tree.item(selected)["values"][0]
        result["canonical_id"] = canonical_id
        root.destroy()

    def _register_new() -> None:
        new_id = _generate_canonical_id(scraped_name, players)
        # Create skeleton record in players — fill in gender/starting_rating manually afterwards
        players[new_id] = {
            "canonical_id":    new_id,
            "display_name":    scraped_name,
            "gender":          None,
            "starting_rating": None
        }
        result["canonical_id"] = new_id
        root.destroy()

    ttk.Button(
        btn_frame,
        text="Link to selected player",
        style="Accent.TButton",
        command=_link_selected
    ).pack(side="left", padx=(0, 8))

    ttk.Button(
        btn_frame,
        text="Register as new player",
        command=_register_new
    ).pack(side="left")

    # ── Keyboard shortcuts ────────────────────
    root.bind("<Return>", lambda _: _link_selected())
    root.bind("<Escape>", lambda _: _on_quit())

    def _on_quit() -> None:
        if messagebox.askokcancel(
            "Quit",
            "Quitting will stop consolidation.\nAll resolutions so far have been saved.",
            parent=root
        ):
            root.destroy()
            raise SystemExit("Consolidation cancelled by user.")

    root.protocol("WM_DELETE_WINDOW", _on_quit)

    # Centre window on screen
    root.update_idletasks()
    w = root.winfo_reqwidth()
    h = root.winfo_reqheight()
    x = (root.winfo_screenwidth()  // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    root.mainloop()

    return result["canonical_id"]
