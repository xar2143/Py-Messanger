from flask import Flask, request, jsonify
import threading
import time
from datetime import datetime
import json
import os
import sys
from pathlib import Path
import tempfile

app = Flask(__name__)

class MessengerServer:
    def __init__(self):
        self.utenti = {}
        self.messaggi = {}
        self.ultimo_ping = {}
        self.lock = threading.Lock()
        self.registered_users = {}
        
        # start percorso file
        self.users_file = self.get_data_file_path()
        print(f"Percorso file utenti: {self.users_file}", file=sys.stderr)
        self.load_users()
        self.avvia_thread_pulizia()

    # 3 opzioni per la folder

    def get_data_file_path(self):
        try:
            # 1 directory nella home dell'utente
            home = Path.home()
            app_dir = home / '.messenger_data'
            
            try:
                # crea la directory se non esiste
                app_dir.mkdir(exist_ok=True)
                file_path = app_dir / 'users.json'

                if not os.access(app_dir, os.W_OK):
                    raise PermissionError("No write access to app directory")
                return file_path
            except Exception as e:
                print(f"Non posso usare la home directory: {e}", file=sys.stderr)
            
            # 2 directory temporanea del sistema
            temp_dir = Path(tempfile.gettempdir()) / 'messenger_data'
            temp_dir.mkdir(exist_ok=True)
            return temp_dir / 'users.json'
            
        except Exception as e:
            print(f"Errore nella creazione del percorso del file: {e}", file=sys.stderr)
            # 3 usa una directory temp
            return Path(tempfile.gettempdir()) / 'messenger_users.json'

    def load_users(self):
        try:
            if self.users_file.exists():
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    self.registered_users = json.load(f)
                print(f"File utenti caricato da: {self.users_file}", file=sys.stderr)
            else:
                self.registered_users = {}
                self.save_users()
                print(f"Creato nuovo file utenti in: {self.users_file}", file=sys.stderr)
                
        except Exception as e:
            print(f"Errore nel caricamento degli utenti: {e}", file=sys.stderr)
            self.registered_users = {}

    def save_users(self):
        try:
            # file temporaneo nella stessa directory del file finale
            temp_fd, temp_path = tempfile.mkstemp(dir=self.users_file.parent)
            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(self.registered_users, f, indent=4, ensure_ascii=False)
                
                # (windows) chiudi il file prima di rinominarlo
                temp_path = Path(temp_path)
                if self.users_file.exists():
                    self.users_file.unlink()
                temp_path.rename(self.users_file)
                
                print(f"File utenti salvato con successo in: {self.users_file}", file=sys.stderr)
                
            except Exception as e:
                # se errore, elimina il file temporaneo se esiste
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise e
                
        except Exception as e:
            print(f"Errore nel salvataggio degli utenti: {e}", file=sys.stderr)
            # salva nella directory temp come ultima risorsa
            try:
                temp_path = Path(tempfile.gettempdir()) / 'messenger_users_emergency.json'
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(self.registered_users, f, indent=4, ensure_ascii=False)
                print(f"File utenti salvato nel percorso di emergenza: {temp_path}", file=sys.stderr)
            except Exception as e2:
                print(f"Errore critico nel salvataggio degli utenti: {e2}", file=sys.stderr)

    def avvia_thread_pulizia(self):
        def pulisci_utenti_inattivi():
            while True:
                time.sleep(60)
                with self.lock:
                    tempo_corrente = time.time()
                    utenti_da_rimuovere = []
                    
                    for nickname, timestamp in self.ultimo_ping.items():
                        if tempo_corrente - timestamp > 90:
                            utenti_da_rimuovere.append(nickname)
                    
                    for nickname in utenti_da_rimuovere:
                        self.rimuovi_utente(nickname)
        
        thread = threading.Thread(target=pulisci_utenti_inattivi, daemon=True)
        thread.start()

    def rimuovi_utente(self, nickname):
        if nickname in self.utenti:
            del self.utenti[nickname]
        if nickname in self.ultimo_ping:
            del self.ultimo_ping[nickname]
        if nickname in self.messaggi:
            del self.messaggi[nickname]

    def formatta_timestamp(self):
        return datetime.now().strftime("%H:%M:%S")

    def register_new_user(self, nickname, password_hash):
        with self.lock:
            if nickname in self.registered_users:
                return False
            self.registered_users[nickname] = {
                'password': password_hash,
                'created_at': datetime.utcnow().isoformat()
            }
            self.save_users()
            return True

    def verify_credentials(self, nickname, password_hash):
        with self.lock:
            if nickname not in self.registered_users:
                return False
            return self.registered_users[nickname]['password'] == password_hash

server = MessengerServer()

@app.route('/registra_utente', methods=['POST'])
def registra_nuovo_utente():
    dati = request.json
    nickname = dati.get('nickname', '').strip()
    password = dati.get('password', '').strip()
    
    if not nickname or not password:
        return jsonify({'messaggio': 'Nickname e password richiesti'}), 400
    
    if server.register_new_user(nickname, password):
        return jsonify({'messaggio': 'Utente registrato con successo'})
    else:
        return jsonify({'messaggio': 'Nickname già in uso'}), 409

@app.route('/login', methods=['POST'])
def login():
    dati = request.json
    nickname = dati.get('nickname', '').strip()
    password = dati.get('password', '').strip()
    
    if not nickname or not password:
        return jsonify({'messaggio': 'Nickname e password richiesti'}), 400
    
    if server.verify_credentials(nickname, password):
        return jsonify({'messaggio': 'Login effettuato con successo'})
    else:
        return jsonify({'messaggio': 'Credenziali non valide'}), 401

@app.route('/registra', methods=['POST'])
def registra_utente():
    dati = request.json
    nickname = dati.get('nickname', '').strip()
    porta = dati.get('porta')
    
    if not nickname or not porta:
        return jsonify({'messaggio': 'Nickname e porta richiesti'}), 400
    
    with server.lock:
        # verifica che l'utente sia registrato
        if nickname not in server.registered_users:
            return jsonify({'messaggio': 'Utente non registrato'}), 401
        
        # verifica che l'utente non sia online
        if nickname in server.utenti:
            return jsonify({'messaggio': 'Utente già connesso'}), 409
        
        server.utenti[nickname] = porta
        server.messaggi[nickname] = []
        server.ultimo_ping[nickname] = time.time()
        
        return jsonify({
            'messaggio': 'Registrazione completata',
            'utenti_online': len(server.utenti)
        })

@app.route('/disconnetti', methods=['POST'])
def disconnetti_utente():
    dati = request.json
    nickname = dati.get('nickname', '').strip()
    
    with server.lock:
        server.rimuovi_utente(nickname)
        return jsonify({'messaggio': 'Disconnesso'})

@app.route('/ping', methods=['POST'])
def ping():
    dati = request.json
    nickname = dati.get('nickname', '').strip()
    
    if not nickname:
        return jsonify({'messaggio': 'Nickname richiesto'}), 400
    
    with server.lock:
        if nickname not in server.utenti:
            return jsonify({'messaggio': 'Utente non trovato'}), 404
        
        server.ultimo_ping[nickname] = time.time()
        return jsonify({
            'messaggio': 'Pong',
            'utenti_online': len(server.utenti)
        })

@app.route('/invia_messaggio', methods=['POST'])
def invia_messaggio():
    dati = request.json
    mittente = dati.get('mittente', '').strip()
    destinatario = dati.get('destinatario', '').strip()
    messaggio = dati.get('messaggio', '').strip()
    
    if not mittente or not destinatario or not messaggio:
        return jsonify({'messaggio': 'Dati incompleti'}), 400
    
    with server.lock:
        if destinatario not in server.utenti:
            return jsonify({'messaggio': 'Destinatario non trovato'}), 404
        
        nuovo_messaggio = {
            'mittente': mittente,
            'messaggio': messaggio,
            'timestamp_str': server.formatta_timestamp()
        }
        
        server.messaggi[destinatario].append(nuovo_messaggio)
        return jsonify({'messaggio': 'Messaggio inviato'})

@app.route('/messaggi/<nickname>', methods=['GET'])
def recupera_messaggi(nickname):
    with server.lock:
        if nickname not in server.utenti:
            return jsonify({'messaggio': 'Utente non autorizzato'}), 401
        
        messaggi = server.messaggi[nickname]
        server.messaggi[nickname] = []
        
        return jsonify({'messaggi': messaggi})

@app.route('/utenti_online', methods=['GET'])
def lista_utenti():
    with server.lock:
        return jsonify({'utenti': list(server.utenti.keys())})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=False, threaded=True)

# Lo so che gli appunti li metteva meglio mio nonno però attualmente non ho molto tempo, prometto che nel prossimo rilascio metto i commenti meglio :)