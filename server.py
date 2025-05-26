from flask import Flask, request, jsonify
import threading
import time
from datetime import datetime
import json

app = Flask(__name__)

class MessengerServer:
    def __init__(self):
        self.utenti = {}
        self.messaggi = {}
        self.ultimo_ping = {}
        self.lock = threading.Lock()
        self.avvia_thread_pulizia()

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

server = MessengerServer()

@app.route('/registra', methods=['POST'])
def registra_utente():
    dati = request.json
    nickname = dati.get('nickname', '').strip()
    porta = dati.get('porta')
    
    if not nickname or not porta:
        return jsonify({'messaggio': 'Nickname e porta richiesti'}), 400
    
    with server.lock:
        if nickname in server.utenti:
            return jsonify({'messaggio': 'Nickname già in uso'}), 409
        
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
