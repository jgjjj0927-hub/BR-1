#!/usr/bin/env python3
"""
Telegram Channel Manager — управляй каналом как в настоящем Telegram.
Зависимости: только стандартная библиотека Python 3.8+
"""
import tkinter as tk
from tkinter import messagebox
import json, threading, time, urllib.request, os
from datetime import datetime

# ── Palette (Telegram Dark) ──────────────────────────────────────────────────
BG_MAIN   = "#17212B"
BG_HEADER = "#0D1923"
BG_INPUT  = "#0D1923"
BG_MY     = "#2B5278"
BG_FIELD  = "#242F3D"
BG_BUBBLE = "#1E2C3A"
ACCENT    = "#5288C1"
TEXT_MAIN = "#F0F0F0"
TEXT_DIM  = "#6C7883"
BORDER    = "#0E1621"

F_MAIN  = ("Segoe UI", 11)
F_BOLD  = ("Segoe UI", 11, "bold")
F_SMALL = ("Segoe UI", 9)
F_TIME  = ("Segoe UI", 8)

_HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE  = os.path.join(_HERE, "tg_manager_config.json")


# ── Telegram Bot API wrapper ──────────────────────────────────────────────────
class TelegramAPI:
    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = str(chat_id)
        self._offset = 0

    def _call(self, method: str, payload: dict = None) -> dict:
        url  = f"https://api.telegram.org/bot{self.token}/{method}"
        data = json.dumps(payload or {}).encode()
        req  = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except Exception as e:
            return {"ok": False, "description": str(e)}

    def get_chat(self):
        return self._call("getChat", {"chat_id": self.chat_id})

    def send(self, text: str):
        return self._call("sendMessage",
                          {"chat_id": self.chat_id, "text": text})

    def edit(self, msg_id: int, text: str):
        return self._call("editMessageText",
                          {"chat_id": self.chat_id,
                           "message_id": msg_id, "text": text})

    def delete(self, msg_id: int):
        return self._call("deleteMessage",
                          {"chat_id": self.chat_id, "message_id": msg_id})

    def poll(self) -> list:
        res = self._call("getUpdates", {
            "offset": self._offset,
            "allowed_updates": ["channel_post"],
            "timeout": 3, "limit": 50
        })
        posts = []
        if res.get("ok"):
            for upd in res["result"]:
                self._offset = max(self._offset, upd["update_id"] + 1)
                cp = upd.get("channel_post")
                if cp and str(cp.get("chat", {}).get("id")) == self.chat_id:
                    posts.append({
                        "id":   cp["message_id"],
                        "text": cp.get("text", "[медиа]"),
                        "date": cp["date"]
                    })
        return posts


# ── Single message bubble ─────────────────────────────────────────────────────
class Bubble(tk.Frame):
    def __init__(self, parent, msg: dict, on_edit, on_delete):
        super().__init__(parent, bg=BG_MAIN)
        self.msg       = msg
        self._on_edit   = on_edit
        self._on_delete = on_delete
        self._txt_var   = tk.StringVar(value=msg["text"])
        self._build()

    def _build(self):
        row = tk.Frame(self, bg=BG_MAIN)
        row.pack(fill="x", padx=14, pady=3)

        # push bubble to right side
        tk.Frame(row, bg=BG_MAIN, width=80).pack(side="left")

        bubble = tk.Frame(row, bg=BG_MY, padx=12, pady=8)
        bubble.pack(side="right", anchor="e")

        lbl = tk.Label(bubble, textvariable=self._txt_var,
                       font=F_MAIN, fg=TEXT_MAIN, bg=BG_MY,
                       wraplength=440, justify="left", anchor="w")
        lbl.pack(anchor="w")

        ts = datetime.fromtimestamp(self.msg["date"]).strftime("%H:%M")
        tk.Label(bubble, text=ts, font=F_TIME, fg=TEXT_DIM,
                 bg=BG_MY).pack(anchor="e")

        menu = tk.Menu(self, tearoff=0,
                       bg="#1C2B3A", fg=TEXT_MAIN,
                       activebackground=ACCENT, activeforeground="white",
                       font=F_MAIN, bd=0, relief="flat")
        menu.add_command(label="✏   Редактировать",
                         command=lambda: self._on_edit(self.msg, self))
        menu.add_command(label="🗑   Удалить",
                         command=lambda: self._on_delete(self.msg, self))
        menu.add_separator()
        menu.add_command(label="📋   Копировать", command=self._copy)

        for w in (row, bubble, lbl):
            w.bind("<Button-3>", lambda e, m=menu: m.tk_popup(e.x_root, e.y_root))
            w.bind("<Double-Button-1>", lambda e: self._on_edit(self.msg, self))

    def set_text(self, text: str):
        self.msg["text"] = text
        self._txt_var.set(text)

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.msg["text"])


# ── Edit dialog ───────────────────────────────────────────────────────────────
class EditDialog(tk.Toplevel):
    def __init__(self, parent, text: str):
        super().__init__(parent)
        self.result = None
        self.title("Редактировать")
        self.configure(bg=BG_MAIN)
        self.geometry("500x210")
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)

        tk.Label(self, text="Изменить текст сообщения:",
                 font=F_MAIN, fg=TEXT_DIM, bg=BG_MAIN
                 ).pack(anchor="w", padx=18, pady=(18, 5))

        self._t = tk.Text(self, height=4, font=F_MAIN,
                          fg=TEXT_MAIN, bg=BG_FIELD,
                          insertbackground=TEXT_MAIN,
                          relief="flat", bd=0, padx=10, pady=8)
        self._t.pack(fill="x", padx=18)
        self._t.insert("1.0", text)
        self._t.focus_set()

        bf = tk.Frame(self, bg=BG_MAIN)
        bf.pack(fill="x", padx=18, pady=14)

        tk.Button(bf, text="  Сохранить  ", font=F_MAIN,
                  fg="white", bg=ACCENT, activebackground="#3A7BD5",
                  bd=0, pady=7, cursor="hand2",
                  command=self._ok).pack(side="right")
        tk.Button(bf, text="  Отмена  ", font=F_MAIN,
                  fg=TEXT_DIM, bg=BG_FIELD, activebackground=BG_BUBBLE,
                  bd=0, pady=7, cursor="hand2",
                  command=self.destroy).pack(side="right", padx=8)

        self.bind("<Return>", lambda e: self._ok())
        self.wait_window()

    def _ok(self):
        self.result = self._t.get("1.0", "end-1c").strip()
        self.destroy()


# ── Settings dialog ───────────────────────────────────────────────────────────
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, cfg: dict, on_save):
        super().__init__(parent)
        self._on_save = on_save
        self.title("Настройки")
        self.configure(bg=BG_MAIN)
        self.geometry("480x280")
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)

        tk.Label(self, text="⚙   Настройки подключения",
                 font=F_BOLD, fg=TEXT_MAIN, bg=BG_MAIN
                 ).pack(pady=(22, 14))

        self._tok = self._row("Bot Token:", cfg.get("token", ""))
        self._cid = self._row("Chat ID:",   cfg.get("chat_id", ""))

        tk.Label(self,
                 text="Формат Chat ID для канала:  -100xxxxxxxxxx",
                 font=F_SMALL, fg=TEXT_DIM, bg=BG_MAIN).pack(pady=4)

        bf = tk.Frame(self, bg=BG_MAIN)
        bf.pack(fill="x", padx=22, pady=22)

        tk.Button(bf, text="  Подключить  ", font=F_MAIN,
                  fg="white", bg=ACCENT, activebackground="#3A7BD5",
                  bd=0, pady=8, cursor="hand2",
                  command=self._save).pack(side="right")
        self.wait_window()

    def _row(self, label, val=""):
        f = tk.Frame(self, bg=BG_MAIN)
        f.pack(fill="x", padx=22, pady=5)
        tk.Label(f, text=label, font=F_MAIN, fg=TEXT_DIM,
                 bg=BG_MAIN, width=12, anchor="w").pack(side="left")
        e = tk.Entry(f, font=F_MAIN, fg=TEXT_MAIN, bg=BG_FIELD,
                     insertbackground=TEXT_MAIN, relief="flat", bd=0)
        e.pack(side="left", fill="x", expand=True, ipady=7, padx=(8, 0))
        if val:
            e.insert(0, val)
        return e

    def _save(self):
        t, c = self._tok.get().strip(), self._cid.get().strip()
        if not t or not c:
            messagebox.showwarning("Внимание", "Заполни все поля!", parent=self)
            return
        self.destroy()
        self._on_save(t, c)


# ── Main window ───────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Telegram Channel Manager")
        self.geometry("740x700")
        self.minsize(480, 420)
        self.configure(bg=BG_MAIN)

        self._cfg: dict        = self._load_cfg()
        self._api: TelegramAPI = None
        self._bubbles: dict    = {}   # msg_id → Bubble

        self._build()

        if self._cfg.get("token") and self._cfg.get("chat_id"):
            self._connect()
        else:
            self.after(100, self._open_settings)

    # ── Persistence ──────────────────────────────────────────────────────────
    def _load_cfg(self):
        try:
            return json.loads(open(CONFIG_FILE).read())
        except:
            return {}

    def _save_cfg(self):
        open(CONFIG_FILE, "w").write(json.dumps(self._cfg, ensure_ascii=False))

    # ── UI Construction ───────────────────────────────────────────────────────
    def _build(self):
        self._build_header()
        self._build_chat()
        self._build_input()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_HEADER, height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Avatar
        av = tk.Canvas(hdr, width=40, height=40, bg=BG_HEADER,
                       highlightthickness=0)
        av.pack(side="left", padx=(16, 0), pady=9)
        av.create_oval(1, 1, 39, 39, fill=ACCENT, outline="")
        av.create_text(20, 20, text="📢", font=("Segoe UI", 16))

        info = tk.Frame(hdr, bg=BG_HEADER)
        info.pack(side="left", padx=12, fill="y", pady=8)

        self._v_title = tk.StringVar(value="Загрузка…")
        tk.Label(info, textvariable=self._v_title, font=F_BOLD,
                 fg=TEXT_MAIN, bg=BG_HEADER).pack(anchor="w")
        self._v_sub = tk.StringVar(value="канал")
        tk.Label(info, textvariable=self._v_sub, font=F_SMALL,
                 fg=TEXT_DIM, bg=BG_HEADER).pack(anchor="w")

        tk.Button(hdr, text="⚙", font=("Segoe UI", 17),
                  fg=TEXT_DIM, bg=BG_HEADER,
                  activebackground=BG_HEADER, activeforeground=ACCENT,
                  bd=0, cursor="hand2",
                  command=self._open_settings).pack(side="right", padx=18)

    def _build_chat(self):
        wrap = tk.Frame(self, bg=BG_MAIN)
        wrap.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(wrap, bg=BG_MAIN,
                                 highlightthickness=0, bd=0)
        sb = tk.Scrollbar(wrap, orient="vertical",
                          command=self._canvas.yview,
                          bg=BG_MAIN, troughcolor=BG_MAIN,
                          activebackground=TEXT_DIM)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._msgs_frame = tk.Frame(self._canvas, bg=BG_MAIN)
        self._cwin = self._canvas.create_window(
            (0, 0), window=self._msgs_frame, anchor="nw")

        self._msgs_frame.bind("<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._cwin, width=e.width))
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(
                int(-1 * e.delta / 120), "units"))

        self._empty = tk.Label(self._msgs_frame,
                               text="Нет сообщений\nНапиши первое!",
                               font=("Segoe UI", 13), fg=TEXT_DIM, bg=BG_MAIN)
        self._empty.pack(expand=True, pady=80)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

    def _build_input(self):
        inp = tk.Frame(self, bg=BG_INPUT, pady=10, padx=14)
        inp.pack(fill="x")

        self._inp = tk.Text(inp, height=1, font=F_MAIN,
                            fg=TEXT_MAIN, bg=BG_FIELD,
                            insertbackground=TEXT_MAIN,
                            relief="flat", bd=0, padx=12, pady=9, wrap="word")
        self._inp.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._ph = "Написать сообщение…"
        self._inp.insert("1.0", self._ph)
        self._inp.config(fg=TEXT_DIM)
        self._inp.bind("<FocusIn>",    self._ph_clear)
        self._inp.bind("<FocusOut>",   self._ph_restore)
        self._inp.bind("<Return>",     self._on_enter)
        self._inp.bind("<Shift-Return>", lambda e: None)
        self._inp.bind("<KeyRelease>", self._auto_h)
        self._inp.bind("<Control-a>",
            lambda e: (self._inp.tag_add("sel", "1.0", "end"), "break")[1])
        self._inp.bind("<Control-A>",
            lambda e: (self._inp.tag_add("sel", "1.0", "end"), "break")[1])

        tk.Button(inp, text="➤", font=("Segoe UI", 20),
                  fg=ACCENT, bg=BG_INPUT,
                  activebackground=BG_INPUT, activeforeground=TEXT_MAIN,
                  bd=0, cursor="hand2",
                  command=self._send).pack(side="right")

    # ── Input helpers ─────────────────────────────────────────────────────────
    def _ph_clear(self, _):
        if self._inp.get("1.0", "end-1c") == self._ph:
            self._inp.delete("1.0", "end")
            self._inp.config(fg=TEXT_MAIN)

    def _ph_restore(self, _):
        if not self._inp.get("1.0", "end-1c").strip():
            self._inp.delete("1.0", "end")
            self._inp.insert("1.0", self._ph)
            self._inp.config(fg=TEXT_DIM)

    def _auto_h(self, _=None):
        lines = int(self._inp.index("end-1c").split(".")[0])
        self._inp.config(height=min(max(lines, 1), 5))

    def _get_text(self):
        t = self._inp.get("1.0", "end-1c").strip()
        return "" if t == self._ph else t

    def _clear_inp(self):
        self._inp.delete("1.0", "end")
        self._inp.config(height=1)
        self._ph_restore(None)

    def _on_enter(self, _):
        self._send()
        return "break"

    # ── Messaging ─────────────────────────────────────────────────────────────
    def _send(self):
        text = self._get_text()
        if not text or not self._api:
            return
        self._clear_inp()

        def _do():
            res = self._api.send(text)
            if res.get("ok"):
                m = res["result"]
                data = {"id": m["message_id"],
                        "text": text, "date": m["date"]}
                self.after(0, lambda: self._add_bubble(data))
            else:
                self.after(0, lambda: messagebox.showerror(
                    "Ошибка отправки", res.get("description", "?")))

        threading.Thread(target=_do, daemon=True).start()

    def _add_bubble(self, msg: dict):
        if msg["id"] in self._bubbles:
            return
        if self._empty:
            self._empty.pack_forget()
            self._empty = None

        b = Bubble(self._msgs_frame, msg,
                   on_edit=self._edit_msg, on_delete=self._delete_msg)
        b.pack(fill="x")
        self._bubbles[msg["id"]] = b
        self.after(60, lambda: self._canvas.yview_moveto(1.0))

    def _edit_msg(self, msg: dict, bubble: Bubble):
        dlg = EditDialog(self, msg["text"])
        new = dlg.result
        if not new or new == msg["text"]:
            return

        def _do():
            res = self._api.edit(msg["id"], new)
            if res.get("ok"):
                self.after(0, lambda: bubble.set_text(new))
            else:
                self.after(0, lambda: messagebox.showerror(
                    "Ошибка редактирования", res.get("description", "?")))

        threading.Thread(target=_do, daemon=True).start()

    def _delete_msg(self, msg: dict, bubble: Bubble):
        if not messagebox.askyesno("Удалить сообщение",
                                   "Удалить это сообщение?", parent=self):
            return

        def _do():
            res = self._api.delete(msg["id"])
            if res.get("ok"):
                self._bubbles.pop(msg["id"], None)
                self.after(0, bubble.destroy)
            else:
                self.after(0, lambda: messagebox.showerror(
                    "Ошибка удаления", res.get("description", "?")))

        threading.Thread(target=_do, daemon=True).start()

    # ── Connection & polling ──────────────────────────────────────────────────
    def _connect(self):
        self._api = TelegramAPI(self._cfg["token"], self._cfg["chat_id"])
        threading.Thread(target=self._fetch_info, daemon=True).start()
        threading.Thread(target=self._poll,       daemon=True).start()

    def _fetch_info(self):
        res = self._api.get_chat()
        if res.get("ok"):
            ch    = res["result"]
            title = ch.get("title", "Канал")
            cnt   = ch.get("members_count")
            sub   = (f"{cnt:,} подписчиков".replace(",", " ")
                     if cnt else "канал")
            self.after(0, lambda: self._v_title.set(title))
            self.after(0, lambda: self._v_sub.set(sub))
            self.after(0, lambda: self.title(f"{title} — Telegram Manager"))

    def _poll(self):
        while True:
            try:
                for post in self._api.poll():
                    if post["id"] not in self._bubbles:
                        self.after(0, lambda p=post: self._add_bubble(p))
            except:
                pass
            time.sleep(3)

    # ── Settings ──────────────────────────────────────────────────────────────
    def _open_settings(self):
        SettingsDialog(self, self._cfg, self._on_settings_saved)

    def _on_settings_saved(self, token: str, chat_id: str):
        self._cfg.update({"token": token, "chat_id": chat_id})
        self._save_cfg()
        self._bubbles.clear()
        for w in self._msgs_frame.winfo_children():
            w.destroy()
        self._connect()


if __name__ == "__main__":
    App().mainloop()
