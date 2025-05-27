import threading
import requests
import json
from flask import Flask, request, jsonify
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import socket
import hashlib

class LoginWindow:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Login Messenger")
        self.window.geometry("300x200")
        self.window.resizable(False, False)
        self.success = False
        self.nickname = None
        
        self.setup_gui()
        
    def setup_gui(self):
        # main frame
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # label titolo
        title_label = ttk.Label(main_frame, text="Login Messenger", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # frame nick
        nick_frame = ttk.Frame(main_frame)
        nick_frame.pack(fill='x', pady=5)
        ttk.Label(nick_frame, text="Nickname:").pack(side='left')
        self.nickname_entry = ttk.Entry(nick_frame)
        self.nickname_entry.pack(side='left', padx=(10, 0), fill='x', expand=True)
        
        # frame pass
        pass_frame = ttk.Frame(main_frame)
        pass_frame.pack(fill='x', pady=5)
        ttk.Label(pass_frame, text="Password:").pack(side='left')
        self.password_entry = ttk.Entry(pass_frame, show="*")
        self.password_entry.pack(side='left', padx=(10, 0), fill='x', expand=True)
        
        # bottoni
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(20, 0))
        
        ttk.Button(btn_frame, text="Login", command=self.login).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Registrati", command=self.registra).pack(side='left', padx=5)
        
        # enter key blind
        self.window.bind('<Return>', lambda e: self.login())
        
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def login(self):
        nickname = self.nickname_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not nickname or not password:
            messagebox.showerror("Errore", "Inserisci nickname e password!")
            return
            
        try:
            url = "http://127.0.0.1:5001/login"
            payload = {
                'nickname': nickname,
                'password': self.hash_password(password)
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                self.success = True
                self.nickname = nickname
                self.window.quit()  
            else:
                messagebox.showerror("Errore", "Credenziali non valide!")
                
        except Exception as e:
            messagebox.showerror("Errore", f"Errore di connessione: {str(e)}")
    
    def registra(self):
        nickname = self.nickname_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not nickname or not password:
            messagebox.showerror("Errore", "Inserisci nickname e password!")
            return
            
        if len(nickname) < 2:
            messagebox.showerror("Errore", "Il nickname deve essere di almeno 2 caratteri!")
            return
            
        if len(password) < 6:
            messagebox.showerror("Errore", "La password deve essere di almeno 6 caratteri!")
            return
            
        try:
            url = "http://127.0.0.1:5001/registra_utente"
            payload = {
                'nickname': nickname,
                'password': self.hash_password(password)
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                messagebox.showinfo("Successo", "Registrazione completata! Ora puoi effettuare il login.")
                self.password_entry.delete(0, tk.END)
            elif response.status_code == 409:
                messagebox.showerror("Errore", "Nickname già in uso!")
            else:
                messagebox.showerror("Errore", "Errore durante la registrazione!")
                
        except Exception as e:
            messagebox.showerror("Errore", f"Errore di connessione: {str(e)}")
    
    def run(self):
        self.window.mainloop()
        return self.success, self.nickname

class MessengerClient:
    def __init__(self):
        # mostra prima la finestra di login (senza si romperebbe tutto)
        login_window = LoginWindow()
        success, nickname = login_window.run()
        
        if not success:  
            return
            
        # distruggi la finestra del log 
        login_window.window.destroy()
        
        self.nickname = nickname
        self.porta_locale = 5000
        self.server_ip = "127.0.0.1"
        self.server_porta = 5001
        self.messaggi = []
        self.connesso = False
        self.utenti_online = []
        
        self.root = tk.Tk()
        self.root.title(f"Messenger Chat - {self.nickname}")
        self.root.geometry("700x550")
        
        self.setup_gui()
        self.avvia_thread_polling()
        self.avvia_thread_keepalive()
        
        self.trova_porta_libera_automatica()
        
        # conetti utente
        self.connetti_chat()

    def trova_porta_libera_automatica(self):
        try:
            sock = socket.socket()
            sock.bind(('', 0))
            self.porta_locale = sock.getsockname()[1]
            sock.close()
        except Exception as e:
            self.porta_locale = 5000

    def setup_gui(self):
        frame_config = ttk.LabelFrame(self.root, text="Accesso Chat")
        frame_config.pack(fill='x', padx=10, pady=10)
        
        row_nickname = ttk.Frame(frame_config)
        row_nickname.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(row_nickname, text="Il tuo nickname:", font=('Arial', 10)).pack(side='left', padx=(0, 10))
        self.entry_nickname = ttk.Entry(row_nickname, width=20, font=('Arial', 10))
        self.entry_nickname.pack(side='left', padx=(0, 15))
        self.entry_nickname.insert(0, self.nickname)
        self.entry_nickname.config(state='disabled')
        
        self.btn_connetti = ttk.Button(row_nickname, text="Entra in Chat", command=self.connetti_chat)
        self.btn_connetti.pack(side='left', padx=10)
        
        self.btn_disconnetti = ttk.Button(row_nickname, text="Esci", command=self.disconnetti_server, state='disabled')
        self.btn_disconnetti.pack(side='left', padx=5)
        
        self.label_stato = ttk.Label(frame_config, text="Non connesso", foreground="red", font=('Arial', 9))
        self.label_stato.pack(pady=(5, 10))
        
        frame_utenti = ttk.LabelFrame(self.root, text="Utenti Online")
        frame_utenti.pack(fill='x', padx=10, pady=5)
        
        list_frame = ttk.Frame(frame_utenti)
        list_frame.pack(fill='x', padx=5, pady=5)
        
        self.listbox_utenti = tk.Listbox(list_frame, height=4, font=('Arial', 9))
        self.listbox_utenti.pack(side='left', fill='both', expand=True)
        self.listbox_utenti.bind('<Double-Button-1>', self.seleziona_da_lista_doppio_click)
        
        scrollbar_utenti = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar_utenti.pack(side='right', fill='y')
        
        self.listbox_utenti.config(yscrollcommand=scrollbar_utenti.set)
        scrollbar_utenti.config(command=self.listbox_utenti.yview)
        
        btn_frame = ttk.Frame(frame_utenti)
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Aggiorna Lista", command=self.aggiorna_utenti_online).pack(side='left')
        ttk.Button(btn_frame, text="Seleziona per Chat", command=self.seleziona_da_lista).pack(side='left', padx=10)
        
        frame_chat = ttk.LabelFrame(self.root, text="Conversazione")
        frame_chat.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.text_chat = scrolledtext.ScrolledText(frame_chat, state='disabled', height=15, font=('Arial', 9))
        self.text_chat.pack(fill='both', expand=True, padx=5, pady=5)
        
        frame_invio = ttk.LabelFrame(self.root, text="Invia Messaggio")
        frame_invio.pack(fill='x', padx=10, pady=5)
        
        row_dest = ttk.Frame(frame_invio)
        row_dest.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(row_dest, text="A:").pack(side='left', padx=(0, 5))
        self.entry_destinatario = ttk.Entry(row_dest, width=20, font=('Arial', 9))
        self.entry_destinatario.pack(side='left', padx=(0, 10), fill='x', expand=True)
        
        row_msg = ttk.Frame(frame_invio)
        row_msg.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(row_msg, text="Messaggio:").pack(side='left', padx=(0, 5))
        self.entry_messaggio = ttk.Entry(row_msg, width=50, font=('Arial', 9))
        self.entry_messaggio.pack(side='left', padx=(0, 10), fill='x', expand=True)
        self.entry_messaggio.bind('<Return>', lambda e: self.invia_messaggio())
        
        self.btn_invia = ttk.Button(row_msg, text="Invia", command=self.invia_messaggio)
        self.btn_invia.pack(side='right')
        
        frame_buttons = ttk.Frame(self.root)
        frame_buttons.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(frame_buttons, text="Pulisci Chat", command=self.pulisci_chat).pack(side='left')

    def connetti_chat(self):
        if self.connesso:
            messagebox.showwarning("Avviso", "Sei già connesso alla chat!")
            return
        
        self.label_stato.config(text="Connessione in corso...", foreground="orange")
        self.btn_connetti.config(state='disabled')
        
        def connetti():
            MAX_TENTATIVI = 3
            for tentativo in range(MAX_TENTATIVI):
                try:
                    url = f"http://{self.server_ip}:{self.server_porta}/registra"
                    payload = {
                        'nickname': self.nickname,
                        'porta': self.porta_locale
                    }
                    
                    response = requests.post(url, json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        self.connesso = True
                        self.root.after(0, lambda: self.connessione_riuscita(data))
                        break
                    else:
                        data = response.json()
                        messaggio_errore = data.get('messaggio', 'Errore sconosciuto')
                        if tentativo == MAX_TENTATIVI - 1:
                            self.root.after(0, lambda: self.connessione_fallita(f"Errore: {messaggio_errore}"))
                        
                except requests.exceptions.Timeout:
                    if tentativo == MAX_TENTATIVI - 1:
                        self.root.after(0, lambda: self.connessione_fallita("Timeout: il server non risponde."))
                except requests.exceptions.ConnectionError as e:
                    if tentativo == MAX_TENTATIVI - 1:
                        self.root.after(0, lambda: self.connessione_fallita("Impossibile connettersi al server."))
                except Exception as e:
                    if tentativo == MAX_TENTATIVI - 1:
                        self.root.after(0, lambda: self.connessione_fallita(f"Errore di connessione: {str(e)}"))
                
                if tentativo < MAX_TENTATIVI - 1:
                    time.sleep(2)
        
        thread = threading.Thread(target=connetti, daemon=True)
        thread.start()
    
    def connessione_riuscita(self, data):
        utenti_count = data.get('utenti_online', 0)
        
        self.label_stato.config(
            text=f"Connesso come '{self.nickname}' - {utenti_count} utenti online", 
            foreground="green"
        )
        
        self.btn_connetti.config(state='disabled')
        self.btn_disconnetti.config(state='normal')
        
        self.aggiungi_messaggio_sistema(f"✓ Connesso alla chat come '{self.nickname}'")
        self.aggiorna_utenti_online()
        
        messagebox.showinfo("Connesso", f"Benvenuto nella chat, {self.nickname}!")
    
    def connessione_fallita(self, messaggio):
        self.label_stato.config(text="Connessione fallita", foreground="red")
        self.btn_connetti.config(state='normal')
        messagebox.showerror("Errore di Connessione", messaggio)
    
    def disconnetti_server(self):
        if not self.connesso:
            return
        
        try:
            url = f"http://{self.server_ip}:{self.server_porta}/disconnetti"
            payload = {'nickname': self.nickname}
            requests.post(url, json=payload, timeout=3)
        except Exception as e:
            pass
        
        self.connesso = False
        self.utenti_online = []
        
        self.btn_connetti.config(state='normal')
        self.btn_disconnetti.config(state='disabled')
        
        self.label_stato.config(text="Disconnesso", foreground="red")
        self.listbox_utenti.delete(0, tk.END)
        self.entry_destinatario.delete(0, tk.END)
        self.aggiungi_messaggio_sistema("✗ Disconnesso dalla chat")

    def avvia_thread_polling(self):
        def polling_loop():
            while True:
                time.sleep(2)
                if self.connesso:
                    self.recupera_messaggi()
        
        polling_thread = threading.Thread(target=polling_loop, daemon=True)
        polling_thread.start()
    
    def avvia_thread_keepalive(self):
        def keepalive_loop():
            while True:
                time.sleep(30)
                if self.connesso:
                    self.invia_keepalive()
        
        keepalive_thread = threading.Thread(target=keepalive_loop, daemon=True)
        keepalive_thread.start()
    
    def invia_keepalive(self):
        try:
            url = f"http://{self.server_ip}:{self.server_porta}/ping"
            payload = {'nickname': self.nickname}
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                utenti_count = data.get('utenti_online', 0)
                
                self.root.after(0, lambda: self.label_stato.config(
                    text=f"Connesso come '{self.nickname}' - {utenti_count} utenti online"
                ))
            else:
                self.root.after(0, self.disconnetti_server)
                
        except Exception:
            pass
    
    def recupera_messaggi(self):
        try:
            url = f"http://{self.server_ip}:{self.server_porta}/messaggi/{self.nickname}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                messaggi = data.get('messaggi', [])
                
                for msg in messaggi:
                    nuovo_msg = {
                        'mittente': msg['mittente'],
                        'messaggio': msg['messaggio'],
                        'timestamp': msg['timestamp_str'],
                        'tipo': 'ricevuto'
                    }
                    self.messaggi.append(nuovo_msg)
                
                if messaggi:
                    self.root.after(0, self.aggiorna_chat)
                    
            elif response.status_code == 401:
                self.root.after(0, self.disconnetti_server)
                
        except Exception:
            pass
    
    def aggiorna_utenti_online(self):
        if not self.connesso:
            return
        
        def aggiorna():
            try:
                url = f"http://{self.server_ip}:{self.server_porta}/utenti_online"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    utenti = data.get('utenti', [])
                    
                    if self.nickname in utenti:
                        utenti.remove(self.nickname)
                    
                    self.utenti_online = utenti
                    self.root.after(0, self.popola_lista_utenti)
                    
            except Exception:
                pass
        
        thread = threading.Thread(target=aggiorna, daemon=True)
        thread.start()
    
    def popola_lista_utenti(self):
        self.listbox_utenti.delete(0, tk.END)
        
        if not self.utenti_online:
            self.listbox_utenti.insert(tk.END, "(Nessun altro utente online)")
        else:
            for utente in self.utenti_online:
                self.listbox_utenti.insert(tk.END, utente)
    
    def seleziona_da_lista(self):
        selection = self.listbox_utenti.curselection()
        if selection:
            utente = self.listbox_utenti.get(selection[0])
            if utente != "(Nessun altro utente online)":
                self.entry_destinatario.delete(0, tk.END)
                self.entry_destinatario.insert(0, utente)
                self.entry_messaggio.focus()
    
    def seleziona_da_lista_doppio_click(self, event):
        self.seleziona_da_lista()
    
    def invia_messaggio(self):
        if not self.connesso:
            messagebox.showwarning("Avviso", "Non sei connesso alla chat!")
            return
        
        destinatario = self.entry_destinatario.get().strip()
        messaggio = self.entry_messaggio.get().strip()
        
        if not destinatario:
            messagebox.showwarning("Avviso", "Seleziona un destinatario!")
            self.entry_destinatario.focus()
            return
        
        if not messaggio:
            messagebox.showwarning("Avviso", "Scrivi un messaggio!")
            self.entry_messaggio.focus()
            return
        
        self.entry_messaggio.delete(0, tk.END)
        
        def invia():
            try:
                url = f"http://{self.server_ip}:{self.server_porta}/invia_messaggio"
                payload = {
                    'mittente': self.nickname,
                    'destinatario': destinatario,
                    'messaggio': messaggio
                }
                
                response = requests.post(url, json=payload, timeout=5)
                
                if response.status_code == 200:
                    nuovo_msg = {
                        'mittente': 'Tu',
                        'destinatario': destinatario,
                        'messaggio': messaggio,
                        'timestamp': time.strftime("%H:%M:%S"),
                        'tipo': 'inviato'
                    }
                    
                    self.messaggi.append(nuovo_msg)
                    self.root.after(0, self.aggiorna_chat)
                    
                elif response.status_code == 404:
                    self.root.after(0, lambda: messagebox.showerror("Errore", f"Utente '{destinatario}' non trovato o offline!"))
                else:
                    data = response.json()
                    errore = data.get('messaggio', 'Errore sconosciuto')
                    self.root.after(0, lambda: messagebox.showerror("Errore", f"Errore invio: {errore}"))
                    
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Errore", f"Errore invio messaggio: {e}"))
        
        thread = threading.Thread(target=invia, daemon=True)
        thread.start()
    
    def aggiorna_chat(self):
        self.text_chat.config(state='normal')
        self.text_chat.delete(1.0, tk.END)
        
        for msg in self.messaggi:
            if msg['tipo'] == 'inviato':
                testo = f"[{msg['timestamp']}] Tu → {msg['destinatario']}: {msg['messaggio']}\n"
                self.text_chat.insert(tk.END, testo, 'inviato')
            elif msg['tipo'] == 'ricevuto':
                testo = f"[{msg['timestamp']}] {msg['mittente']}: {msg['messaggio']}\n"
                self.text_chat.insert(tk.END, testo, 'ricevuto')
            else:
                testo = f"[{msg['timestamp']}] {msg['messaggio']}\n"
                self.text_chat.insert(tk.END, testo, 'sistema')
        
        self.text_chat.tag_config('inviato', foreground='blue')
        self.text_chat.tag_config('ricevuto', foreground='green')
        self.text_chat.tag_config('sistema', foreground='gray', font=('Arial', 8, 'italic'))
        
        self.text_chat.config(state='disabled')
        self.text_chat.see(tk.END)
    
    def aggiungi_messaggio_sistema(self, messaggio):
        msg_sistema = {
            'messaggio': messaggio,
            'timestamp': time.strftime("%H:%M:%S"),
            'tipo': 'sistema'
        }
        self.messaggi.append(msg_sistema)
        self.aggiorna_chat()
    
    def pulisci_chat(self):
        if messagebox.askyesno("Conferma", "Vuoi davvero pulire tutta la chat?"):
            self.messaggi = []
            self.aggiorna_chat()
    
    def avvia(self):
        if hasattr(self, 'root'):  
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
    
    def on_closing(self):
        if self.connesso:
            self.disconnetti_server()
        self.root.destroy()

if __name__ == "__main__":
    client = MessengerClient()
    client.avvia()

# Lo so che gli appunti li metteva meglio mio nonno però attualmente non ho molto tempo, prometto che nel prossimo rilascio metto i commenti meglio :)