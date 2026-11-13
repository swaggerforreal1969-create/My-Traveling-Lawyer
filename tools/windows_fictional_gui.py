"""Fictional-only desktop GUI. Never use real client data or connect to HTTP."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from src.offline_pilot import initialize_fictional_pilot, open_fictional_pilot
# PyInstaller must see the GUI statically; offline_pilot imports it dynamically.
from src.local_operator_gui import launch_gui  # noqa: F401
from src.fictional_pilot_backup import backup_fictional_pilot, restore_fictional_pilot

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

def backup_case(root):
    """Make one authenticated, credential-free fictional backup. Never overwrite."""
    database = filedialog.askopenfilename(
        parent=root, title="Choose practice case to back up",
        filetypes=[("Practice file", "*.sqlite3")])
    if not database:
        return
    destination = filedialog.asksaveasfilename(
        parent=root, title="Save practice backup as",
        defaultextension=".json",
        filetypes=[("Practice backup", "*.json")])
    if not destination:
        return
    path = Path(destination)
    if path.exists() or path.is_symlink():
        messagebox.showerror(TITLE, "Backup file already exists. No changes were made.", parent=root)
        return
    token = simpledialog.askstring(
        TITLE, "Practice owner access code (hidden):", show="*", parent=root)
    if not token:
        return
    try:
        result = backup_fictional_pilot(Path(database), token, path)
    except Exception:
        messagebox.showerror(
            TITLE,
            "Backup denied or unavailable. Nothing was confirmed as saved. "
            "Do not overwrite an existing file or retry an uncertain write.",
            parent=root)
        return
    finally:
        del token
    messagebox.showinfo(
        TITLE,
        "Practice backup saved. It is not encrypted. Keep it private. "
        "Do not use real client information. Independently check your saved file.",
        parent=root)


def restore_case(root):
    """Restore fictional records to an UNUSED file and issue new private codes."""
    archive = filedialog.askopenfilename(
        parent=root, title="Choose practice backup to restore",
        filetypes=[("Practice backup", "*.json")])
    if not archive:
        return
    destination = filedialog.asksaveasfilename(
        parent=root, title="Save restored practice case as",
        defaultextension=".sqlite3",
        filetypes=[("Practice file", "*.sqlite3")])
    if not destination:
        return
    path = Path(destination)
    if path.exists() or path.is_symlink():
        messagebox.showerror(
            TITLE, "That practice file already exists. No changes were made.", parent=root)
        return
    if not messagebox.askyesno(
        TITLE,
        "Restore only fictional practice data to a NEW file?\n"
        "The old access codes will NOT work. New codes will appear once.\n"
        "Do not use client information.",
        parent=root):
        return
    try:
        result = restore_fictional_pilot(Path(archive), path)
    except Exception:
        messagebox.showerror(
            TITLE, "Restore denied or unavailable. No restored practice is confirmed. "
            "Do not repeat an uncertain restore.", parent=root)
        return
    window = tk.Toplevel(root)
    window.title("Save NEW restored practice access codes")
    window.transient(root)
    window.grab_set()
    tk.Label(
        window,
        text="These NEW codes appear once. Store them privately. Old codes will not work.").pack(
        padx=15,pady=15)
    for account in result["accounts"]:
        tk.Label(window, text=account["user"]).pack()
        code = tk.Entry(window, width=72)
        code.insert(0, account["token"])
        code.configure(state="readonly")
        code.pack(padx=15,pady=5)
    tk.Button(window,text="I saved the NEW codes",command=window.destroy).pack(pady=12)
    root.wait_window(window)


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
        "7. Select Back Up Practice Case to save a fictional case. Use the owner code.\\n"
        "8. Backups are NOT encrypted. Store the backup file privately.\\n"
        "9. Select Restore Practice Backup to restore into a NEW, unused file.\\n"
        "10. Save the NEW access codes. Old codes will not open the restored case.\\n"
        "11. Never overwrite an existing case or retry an uncertain restore.\\n"
        "12. Select Close when finished.",
        parent=root)

def main():
    root=tk.Tk()
    root.title(TITLE)
    root.geometry("440x410")
    root.resizable(False,False)
    tk.Label(root,text="My Traveling Lawyer",font=("Segoe UI",19,"bold")).pack(pady=(20,8))
    tk.Label(root,text="Practice only. Never use real client information.").pack(pady=(0,16))
    tk.Button(root,text="Create Practice Case",width=28,height=2,command=lambda:create_case(root)).pack(pady=5)
    tk.Button(root,text="Open Practice Case",width=28,height=2,command=lambda:choose_case(root)).pack(pady=5)
    tk.Button(root,text="Practice Help",width=28,command=lambda:show_practice_help(root)).pack(pady=3)
    tk.Button(root,text="Back Up Practice Case",width=28,command=lambda:backup_case(root)).pack(pady=3)
    tk.Button(root,text="Restore Practice Backup",width=28,command=lambda:restore_case(root)).pack(pady=3)
    tk.Button(root,text="Close",command=root.destroy).pack(pady=10)
    root.mainloop()
if __name__=="__main__":
    main()
