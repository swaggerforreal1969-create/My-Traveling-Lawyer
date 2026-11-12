"""Fictional-only desktop GUI. Never use real client data or connect to HTTP."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from src.offline_pilot import initialize_fictional_pilot, open_fictional_pilot
# PyInstaller must see the GUI statically; offline_pilot imports it dynamically.
from src.local_operator_gui import launch_gui  # noqa: F401

TITLE = "My Traveling Lawyer — Fictional Practice"

def open_case(root, database, code=None):
    code = code or simpledialog.askstring(TITLE, "Practice access code:", show="*", parent=root)
    if not code:
        return
    try:
        root.withdraw()
        open_fictional_pilot(Path(database), code)
    except Exception:
        messagebox.showerror(TITLE, "Access denied or case could not open.", parent=root)
    finally:
        root.deiconify()

def create_case(root):
    name = filedialog.asksaveasfilename(parent=root, title="Save a new practice case",
        defaultextension=".sqlite3", filetypes=[("Practice file", "*.sqlite3")])
    if not name:
        return
    path = Path(name)
    if path.exists() or path.is_symlink():
        messagebox.showerror(TITLE, "That file exists. No changes were made.", parent=root)
        return
    try:
        result = initialize_fictional_pilot(path)
    except Exception:
        messagebox.showerror(TITLE, "Could not make a new practice case.", parent=root)
        return
    window = tk.Toplevel(root)
    window.title("Save your practice access codes")
    window.transient(root)
    window.grab_set()
    tk.Label(window, text="Write down both practice codes now. They will not be shown again.").pack(padx=15,pady=15)
    for title,key in (("Attorney code","editor_token"),("Second reviewer code","reviewer_token")):
        tk.Label(window,text=title).pack()
        entry=tk.Entry(window,width=72)
        entry.insert(0,result[key])
        entry.configure(state="readonly")
        entry.pack(padx=15,pady=5)
    tk.Button(window,text="I saved both codes",command=window.destroy).pack(pady=14)
    root.wait_window(window)
    open_case(root,path,result["editor_token"])

def choose_case(root):
    name=filedialog.askopenfilename(parent=root,title="Open a practice case",
        filetypes=[("Practice file","*.sqlite3")])
    if name:
        open_case(root,name)

def show_practice_help(root):
    """Plain-language instructions for fictional, offline practice only."""
    messagebox.showinfo(
        TITLE,
        "1. Choose Create Practice Case to make a new practice file.\n"
        "2. Save both access codes somewhere private. They will not appear again.\n"
        "3. Choose Open Practice Case to open an existing practice file.\n"
        "4. Only use made-up information. Never enter real client details.\n"
        "5. The second reviewer's code belongs to another authorized person.\n"
        "6. If you see an uncertain result, stop. Do not repeat the action.\n"
        "7. Select Close when finished.",
        parent=root)

def main():
    root=tk.Tk()
    root.title(TITLE)
    root.geometry("440x290")
    root.resizable(False,False)
    tk.Label(root,text="My Traveling Lawyer",font=("Segoe UI",19,"bold")).pack(pady=(20,8))
    tk.Label(root,text="Practice only. Never use real client information.").pack(pady=(0,16))
    tk.Button(root,text="Create Practice Case",width=28,height=2,command=lambda:create_case(root)).pack(pady=5)
    tk.Button(root,text="Open Practice Case",width=28,height=2,command=lambda:choose_case(root)).pack(pady=5)
    tk.Button(root,text="Practice Help",width=28,command=lambda:show_practice_help(root)).pack(pady=3)
    tk.Button(root,text="Close",command=root.destroy).pack(pady=10)
    root.mainloop()
if __name__=="__main__":
    main()
