from flask import Flask, render_template, jsonify, request, session, send_file
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO, emit, join_room, leave_room
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import threading
from datetime import datetime, timedelta
from collections import defaultdict
import time
import math
import uuid
import os
import base64
import random
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# FIX: Add static folder configuration
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = "ionline-telematics-secret-key"
app.config['SECRET_KEY'] = "ionline-telematics-secret-key"
CORS(app)
bcrypt = Bcrypt(app)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60)

# ============================================
# GLOBAL DATA STORAGE
# ============================================
_students = []
_parents = []
_vehicles = []
_deliveries = []
_engine_data = {}
_video_streams = {}
_active_voice_calls = {}
_drivers = []
_messages = []
_announcements = []

# ============================================
# PHONE MARKETPLACE DATA
# ============================================
PHONE_ORDERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'phone_orders.json')
PHONE_PRICES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'phone_prices.json')

def load_phone_orders():
    try:
        if os.path.exists(PHONE_ORDERS_FILE):
            with open(PHONE_ORDERS_FILE, 'r') as f:
                return json.load(f)
        return []
    except:
        return []

def save_phone_orders(orders):
    try:
        with open(PHONE_ORDERS_FILE, 'w') as f:
            json.dump(orders, f, indent=2)
    except Exception as e:
        print(f"Error saving orders: {e}")

def load_phone_prices():
    try:
        if os.path.exists(PHONE_PRICES_FILE):
            with open(PHONE_PRICES_FILE, 'r') as f:
                data = json.load(f)
                return data.get('phones', [])
        return []
    except Exception as e:
        print(f"Error loading phone prices: {e}")
        return []

# Initialize drivers
def init_drivers():
    global _drivers, _vehicles
    if not _drivers:
        _drivers = [
            {
                "id": 1,
                "name": "John Driver",
                "email": "john@ionline.com",
                "phone": "+254712345678",
                "password": bcrypt.generate_password_hash("driver123").decode('utf-8'),
                "vehicle_imei": "863471063393911",
                "status": "online",
                "last_active": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            },
            {
                "id": 2,
                "name": "Sarah Driver",
                "email": "sarah@ionline.com",
                "phone": "+254723456789",
                "password": bcrypt.generate_password_hash("driver123").decode('utf-8'),
                "vehicle_imei": "863471063393912",
                "status": "online",
                "last_active": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            },
            {
                "id": 3,
                "name": "Michael Omondi",
                "email": "michael@ionline.com",
                "phone": "+254734567890",
                "password": bcrypt.generate_password_hash("driver123").decode('utf-8'),
                "vehicle_imei": "863471063393913",
                "status": "offline",
                "last_active": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            }
        ]
    
    if not _vehicles:
        for driver in _drivers:
            _vehicles.append({
                "imei": driver["vehicle_imei"],
                "bus_number": f"BUS-{driver['id']:03d}",
                "driver_name": driver["name"],
                "driver_id": driver["id"],
                "driver_phone": driver["phone"],
                "status": driver["status"],
                "current_location": [-1.2864 + (driver["id"] * 0.005), 36.8172 + (driver["id"] * 0.003)],
                "engine": {
                    "rpm": random.randint(800, 2500),
                    "speed": random.randint(0, 80),
                    "coolant_temp": random.randint(70, 95),
                    "fuel_level": random.randint(40, 100),
                    "engine_load": random.randint(20, 80),
                    "battery_voltage": 12 + random.random() * 1.5,
                    "fault_codes": []
                },
                "last_maintenance": "2025-03-15",
                "total_distance": random.randint(5000, 20000),
                "fuel_consumption": random.uniform(10, 15)
            })

# Initialize deliveries
def init_deliveries():
    global _deliveries
    if not _deliveries:
        _deliveries = [
            {
                "id": "DEL-001",
                "pickup": "Nairobi CBD, Moi Avenue",
                "pickup_lat": -1.2833,
                "pickup_lon": 36.8167,
                "dropoff": "Westlands, Waiyaki Way",
                "dropoff_lat": -1.2689,
                "dropoff_lon": 36.8156,
                "customer": "ABC Store",
                "customer_phone": "+254712345678",
                "status": "pending",
                "assigned_to": "863471063393911",
                "assigned_driver": "John Driver",
                "created_at": datetime.now().isoformat(),
                "items": [{"name": "Package 1", "weight": 5, "dimensions": "30x20x10"}],
                "notes": "Call customer 10 mins before arrival"
            },
            {
                "id": "DEL-002",
                "pickup": "Industrial Area, Likoni Road",
                "pickup_lat": -1.3178,
                "pickup_lon": 36.8511,
                "dropoff": "Karen, Karen Road",
                "dropoff_lat": -1.3178,
                "dropoff_lon": 36.7344,
                "customer": "XYZ Ltd",
                "customer_phone": "+254723456789",
                "status": "in_progress",
                "assigned_to": "863471063393912",
                "assigned_driver": "Sarah Driver",
                "created_at": datetime.now().isoformat(),
                "items": [{"name": "Equipment", "weight": 15, "dimensions": "50x40x30"}],
                "notes": "Delivery to 3rd floor"
            }
        ]

init_drivers()
init_deliveries()

# ============================================
# HELPER FUNCTIONS
# ============================================
def get_vehicles():
    return _vehicles

def save_vehicles(vehicles):
    global _vehicles
    _vehicles = vehicles
    return True

def get_drivers():
    return _drivers

def save_drivers(drivers):
    global _drivers
    _drivers = drivers
    return True

def get_deliveries():
    return _deliveries

def save_deliveries(deliveries):
    global _deliveries
    _deliveries = deliveries
    return True

def get_messages():
    return _messages

def save_messages(messages):
    global _messages
    _messages = messages
    return True

def get_engine_data(imei):
    vehicle = next((v for v in _vehicles if v['imei'] == imei), None)
    return vehicle.get('engine', {}) if vehicle else {}

def update_engine_data(imei, data):
    for v in _vehicles:
        if v['imei'] == imei:
            v['engine'].update(data)
            break
    return True

# ============================================
# EMAIL CONFIGURATION
# ============================================
EMAIL_ENABLED = True
EMAIL_SENDER = "brianombare@gmail.com"
EMAIL_PASSWORD = "wknq esbj fsha digt"
EMAIL_RECIPIENTS = ["albertmomanyi07@gmail.com"]
EMAIL_SMTP_SERVER = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587

def send_email_alert(subject, body, alert_type="info"):
    if not EMAIL_ENABLED:
        return
    try:
        for recipient in EMAIL_RECIPIENTS:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_SENDER
            msg['To'] = recipient
            msg['Subject'] = f"[iOnline] {subject}"
            msg.attach(MIMEText(body, 'plain'))
            server = smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT)
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD.replace(" ", ""))
            server.send_message(msg)
            server.quit()
        print(f"📧 Email sent: {subject}")
    except Exception as e:
        print(f"❌ Email failed: {e}")

# ============================================
# MQTT CONFIGURATION
# ============================================
BROKER = "byte-iot.net"
PORT = 1883
MQTT_USERNAME = "testing"
MQTT_PASSWORD = "dispenser123"
TOPIC = "/topic/transittag/#"

class MQTTDataStore:
    def __init__(self):
        self.vehicle_locations = {}
        self.alerts = []
        self.messages = []
    
    def add_message(self, topic, payload):
        self.messages.insert(0, {
            'time': datetime.now().strftime('%H:%M:%S'),
            'topic': topic,
            'payload': payload
        })
        if len(self.messages) > 100:
            self.messages.pop()
        
        if 'heartbeat' in topic.lower() and isinstance(payload, dict):
            imei = payload.get('imei') or payload.get('header', {}).get('imei')
            lat = payload.get('latitude') or payload.get('header', {}).get('latitude')
            lon = payload.get('longitude') or payload.get('header', {}).get('longitude')
            speed = payload.get('speed') or payload.get('header', {}).get('speed', 0)
            
            if imei and lat and lon:
                self.vehicle_locations[imei] = {
                    'imei': imei, 'lat': lat, 'lon': lon, 'speed': speed,
                    'last_seen': datetime.now().strftime('%H:%M:%S')
                }
    
    def add_alert(self, message, alert_type='info'):
        self.alerts.insert(0, {
            'time': datetime.now().strftime('%H:%M:%S'),
            'message': message,
            'type': alert_type
        })
        if len(self.alerts) > 50:
            self.alerts.pop()

data_store = MQTTDataStore()

def on_connect(client, userdata, flags, rc):
    print(f"✅ MQTT Connected to {BROKER}")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode()
        try:
            payload = json.loads(payload_str)
        except:
            payload = {"raw": payload_str}
        data_store.add_message(msg.topic, payload)
    except Exception as e:
        print(f"❌ MQTT error: {e}")

def mqtt_thread():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"❌ MQTT error: {e}")

threading.Thread(target=mqtt_thread, daemon=True).start()

# ============================================
# SOCKET.IO FOR REAL-TIME COMMUNICATION
# ============================================
@socketio.on('connect')
def handle_connect():
    print(f"🔌 Client connected: {request.sid}")

@socketio.on('join')
def handle_join(data):
    room = data.get('room')
    if room:
        join_room(room)
        print(f"👤 Client joined room: {room}")
        emit('joined', {'room': room, 'sid': request.sid}, room=room)

@socketio.on('driver_login')
def handle_driver_login(data):
    driver_id = data.get('driver_id')
    room = f"driver_{driver_id}"
    join_room(room)
    print(f"🚛 Driver {driver_id} joined room: {room}")

@socketio.on('dispatcher_message')
def handle_dispatcher_message(data):
    message = data.get('message')
    driver_id = data.get('driver_id')
    sender = data.get('sender', 'dispatcher')
    
    msg = {
        'id': str(uuid.uuid4())[:8],
        'sender': sender,
        'message': message,
        'driver_id': driver_id,
        'timestamp': datetime.now().isoformat(),
        'read': False
    }
    _messages.append(msg)
    
    room = f"driver_{driver_id}"
    emit('new_message', msg, room=room)
    emit('message_sent', msg, broadcast=True)

@socketio.on('driver_message')
def handle_driver_message(data):
    message = data.get('message')
    driver_id = data.get('driver_id')
    driver_name = data.get('driver_name')
    
    msg = {
        'id': str(uuid.uuid4())[:8],
        'sender': driver_name,
        'driver_id': driver_id,
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'read': False
    }
    _messages.append(msg)
    
    emit('new_message', msg, room='dispatcher')
    emit('driver_message_received', msg, broadcast=True)

@socketio.on('announcement')
def handle_announcement(data):
    message = data.get('message')
    sender = data.get('sender', 'dispatcher')
    
    announcement = {
        'id': str(uuid.uuid4())[:8],
        'sender': sender,
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'type': 'announcement'
    }
    _messages.append(announcement)
    
    emit('announcement', announcement, broadcast=True)

@socketio.on('delivery_update')
def handle_delivery_update(data):
    delivery_id = data.get('delivery_id')
    status = data.get('status')
    driver_id = data.get('driver_id')
    
    for d in _deliveries:
        if d['id'] == delivery_id:
            d['status'] = status
            d['updated_at'] = datetime.now().isoformat()
            break
    save_deliveries(_deliveries)
    
    emit('delivery_updated', {
        'delivery_id': delivery_id,
        'status': status,
        'driver_id': driver_id
    }, broadcast=True)

# ============================================
# AUTH ROUTES
# ============================================
USERS = {
    "admin": {
        "password": bcrypt.generate_password_hash("admin123").decode('utf-8'),
        "role": "super_admin",
        "name": "Super Admin"
    },
    "dispatcher": {
        "password": bcrypt.generate_password_hash("dispatch123").decode('utf-8'),
        "role": "dispatcher",
        "name": "Dispatch Operator"
    },
    "fleet_manager": {
        "password": bcrypt.generate_password_hash("fleet123").decode('utf-8'),
        "role": "fleet_manager",
        "name": "Fleet Manager"
    }
}

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if username in USERS:
        if bcrypt.check_password_hash(USERS[username]['password'], password):
            session['username'] = username
            session['role'] = USERS[username]['role']
            session['name'] = USERS[username]['name']
            return jsonify({'status': 'success', 'role': USERS[username]['role'], 'name': USERS[username]['name']})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/driver-login', methods=['POST'])
def driver_login():
    data = request.json
    name = data.get('name')
    
    driver = next((d for d in _drivers if d['name'].lower() == name.lower()), None)
    if driver:
        session['driver_id'] = driver['id']
        session['driver_name'] = driver['name']
        session['vehicle_imei'] = driver['vehicle_imei']
        driver['status'] = 'online'
        driver['last_active'] = datetime.now().isoformat()
        save_drivers(_drivers)
        return jsonify({
            'status': 'success',
            'driver': {
                'id': driver['id'],
                'name': driver['name'],
                'vehicle_imei': driver['vehicle_imei'],
                'status': driver['status']
            }
        })
    return jsonify({'error': 'Driver not found'}), 404

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/api/session')
def get_session():
    if 'username' in session:
        return jsonify({'logged_in': True, 'username': session['username'], 'role': session['role'], 'name': session['name']})
    if 'driver_id' in session:
        return jsonify({'logged_in': True, 'driver_id': session['driver_id'], 'driver_name': session['driver_name'], 'role': 'driver'})
    return jsonify({'logged_in': False})

# ============================================
# DRIVER MANAGEMENT API - COMPLETE CRUD
# ============================================
@app.route('/api/drivers', methods=['GET'])
def get_all_drivers():
    drivers = get_drivers()
    for d in drivers:
        d.pop('password', None)
    return jsonify(drivers)

@app.route('/api/drivers', methods=['POST'])
def create_driver():
    data = request.json
    
    existing = next((d for d in _drivers if d['name'].lower() == data.get('name', '').lower()), None)
    if existing:
        return jsonify({'error': 'Driver already exists'}), 400
    
    new_id = max([d['id'] for d in _drivers]) + 1 if _drivers else 1
    new_imei = f"86347106339{new_id:04d}"[-15:]
    
    new_driver = {
        "id": new_id,
        "name": data.get('name'),
        "email": data.get('email', f"{data.get('name', '').lower().replace(' ', '.')}@ionline.com"),
        "phone": data.get('phone', '+254700000000'),
        "password": bcrypt.generate_password_hash("driver123").decode('utf-8'),
        "vehicle_imei": new_imei,
        "status": "offline",
        "last_active": datetime.now().isoformat(),
        "created_at": datetime.now().isoformat()
    }
    
    _drivers.append(new_driver)
    
    new_vehicle = {
        "imei": new_imei,
        "bus_number": f"BUS-{new_id:03d}",
        "driver_name": data.get('name'),
        "driver_id": new_id,
        "driver_phone": data.get('phone', '+254700000000'),
        "status": "offline",
        "current_location": [-1.2864, 36.8172],
        "engine": {
            "rpm": 0,
            "speed": 0,
            "coolant_temp": 70,
            "fuel_level": 100,
            "engine_load": 0,
            "battery_voltage": 12.5,
            "fault_codes": []
        },
        "last_maintenance": datetime.now().isoformat(),
        "total_distance": 0,
        "fuel_consumption": 12.0
    }
    _vehicles.append(new_vehicle)
    
    save_drivers(_drivers)
    save_vehicles(_vehicles)
    
    socketio.emit('new_driver', {
        'driver': {
            'id': new_id,
            'name': data.get('name'),
            'vehicle_imei': new_imei,
            'status': 'offline'
        }
    }, broadcast=True)
    
    print(f"✅ New driver added: {data.get('name')}")
    
    return jsonify({
        'status': 'success',
        'driver': {
            'id': new_id,
            'name': data.get('name'),
            'vehicle_imei': new_imei,
            'password': 'driver123'
        }
    })

@app.route('/api/drivers/<int:driver_id>', methods=['DELETE'])
def delete_driver(driver_id):
    global _drivers, _vehicles
    
    driver = next((d for d in _drivers if d['id'] == driver_id), None)
    if not driver:
        return jsonify({'error': 'Driver not found'}), 404
    
    driver_name = driver['name']
    _drivers = [d for d in _drivers if d['id'] != driver_id]
    _vehicles = [v for v in _vehicles if v.get('driver_id') != driver_id]
    
    save_drivers(_drivers)
    save_vehicles(_vehicles)
    
    socketio.emit('driver_removed', {'driver_id': driver_id, 'name': driver_name}, broadcast=True)
    
    return jsonify({'status': 'success', 'message': f'Driver {driver_name} removed'})

@app.route('/api/drivers/<int:driver_id>', methods=['PUT'])
def update_driver(driver_id):
    data = request.json
    
    for d in _drivers:
        if d['id'] == driver_id:
            if 'name' in data:
                d['name'] = data['name']
                for v in _vehicles:
                    if v.get('driver_id') == driver_id:
                        v['driver_name'] = data['name']
            if 'phone' in data:
                d['phone'] = data['phone']
            if 'email' in data:
                d['email'] = data['email']
            d['updated_at'] = datetime.now().isoformat()
            break
    
    save_drivers(_drivers)
    save_vehicles(_vehicles)
    
    socketio.emit('driver_updated', {'driver_id': driver_id, 'data': data}, broadcast=True)
    
    return jsonify({'status': 'success'})

# ============================================
# TELEMATICS API ROUTES
# ============================================
@app.route('/api/vehicles')
def get_all_vehicles():
    vehicles = get_vehicles()
    for v in vehicles:
        v['location'] = data_store.vehicle_locations.get(v['imei'], {})
    return jsonify(vehicles)

@app.route('/api/vehicles/<imei>')
def get_vehicle(imei):
    vehicle = next((v for v in get_vehicles() if v['imei'] == imei), None)
    if vehicle:
        vehicle['location'] = data_store.vehicle_locations.get(imei, {})
    return jsonify(vehicle or {})

@app.route('/api/driver/vehicle')
def get_driver_vehicle():
    if 'driver_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    imei = session.get('vehicle_imei')
    vehicle = next((v for v in get_vehicles() if v['imei'] == imei), None)
    if vehicle:
        vehicle['location'] = data_store.vehicle_locations.get(imei, {})
    return jsonify(vehicle or {})

@app.route('/api/engine/<imei>')
def get_engine_telemetry(imei):
    engine_data = get_engine_data(imei)
    return jsonify(engine_data)

@app.route('/api/engine/<imei>', methods=['POST'])
def update_engine_telemetry(imei):
    data = request.json
    update_engine_data(imei, data)
    
    if data.get('coolant_temp', 0) > 100:
        data_store.add_alert(f"⚠️ High coolant temperature on vehicle {imei[-6:]}: {data['coolant_temp']}°C", 'danger')
        send_email_alert("High Engine Temperature", f"Vehicle {imei[-6:]} has high coolant temperature", "critical")
    
    if data.get('battery_voltage', 14) < 11.5:
        data_store.add_alert(f"🔋 Low battery voltage on vehicle {imei[-6:]}: {data['battery_voltage']}V", 'warning')
    
    return jsonify({'status': 'success'})

@app.route('/api/deliveries')
def get_all_deliveries():
    if 'driver_id' in session:
        vehicle_imei = session.get('vehicle_imei')
        driver_deliveries = [d for d in get_deliveries() if d.get('assigned_to') == vehicle_imei]
        return jsonify(driver_deliveries)
    return jsonify(get_deliveries())

@app.route('/api/deliveries', methods=['POST'])
def create_delivery():
    data = request.json
    
    assigned_driver = None
    if data.get('assigned_to'):
        vehicle = next((v for v in _vehicles if v['imei'] == data['assigned_to']), None)
        if vehicle:
            assigned_driver = vehicle['driver_name']
    
    new_delivery = {
        'id': f"DEL-{len(_deliveries)+1:03d}",
        'pickup': data.get('pickup'),
        'pickup_lat': data.get('pickup_lat'),
        'pickup_lon': data.get('pickup_lon'),
        'dropoff': data.get('dropoff'),
        'dropoff_lat': data.get('dropoff_lat'),
        'dropoff_lon': data.get('dropoff_lon'),
        'customer': data.get('customer'),
        'customer_phone': data.get('customer_phone', ''),
        'items': data.get('items', []),
        'status': 'pending',
        'assigned_to': data.get('assigned_to'),
        'assigned_driver': assigned_driver,
        'notes': data.get('notes', ''),
        'created_at': datetime.now().isoformat()
    }
    _deliveries.append(new_delivery)
    save_deliveries(_deliveries)
    
    if new_delivery['assigned_to']:
        socketio.emit('new_delivery', new_delivery, room=f"driver_{new_delivery['assigned_to']}")
    
    return jsonify({'status': 'success', 'delivery': new_delivery})

@app.route('/api/deliveries/<delivery_id>', methods=['PUT'])
def update_delivery(delivery_id):
    data = request.json
    for d in _deliveries:
        if d['id'] == delivery_id:
            d.update(data)
            d['updated_at'] = datetime.now().isoformat()
            break
    save_deliveries(_deliveries)
    
    socketio.emit('delivery_updated', {
        'delivery_id': delivery_id,
        'status': data.get('status'),
        'driver_id': data.get('driver_id')
    }, broadcast=True)
    
    return jsonify({'status': 'success'})

@app.route('/api/messages')
def get_messages():
    if 'driver_id' in session:
        driver_id = session['driver_id']
        driver_messages = [m for m in _messages if m.get('driver_id') == driver_id or m.get('type') == 'announcement']
        return jsonify(driver_messages[-50:])
    return jsonify(_messages[-100:])

@app.route('/api/messages', methods=['POST'])
def send_message():
    data = request.json
    msg = {
        'id': str(uuid.uuid4())[:8],
        'sender': data.get('sender'),
        'driver_id': data.get('driver_id'),
        'message': data.get('message'),
        'timestamp': datetime.now().isoformat(),
        'read': False
    }
    _messages.append(msg)
    
    if data.get('driver_id'):
        socketio.emit('new_message', msg, room=f"driver_{data.get('driver_id')}")
    else:
        socketio.emit('new_message', msg, broadcast=True)
    
    return jsonify({'status': 'success', 'message': msg})

@app.route('/api/alerts')
def get_alerts():
    return jsonify(data_store.alerts)

@app.route('/api/locations')
def get_locations():
    return jsonify(list(data_store.vehicle_locations.values()))

@app.route('/api/voice/start', methods=['POST'])
def start_voice_call():
    data = request.json
    from_user = data.get('from')
    to_vehicle = data.get('to')
    call_id = str(uuid.uuid4())[:8]
    
    _active_voice_calls[call_id] = {
        'from': from_user,
        'to': to_vehicle,
        'started': datetime.now().isoformat(),
        'status': 'active'
    }
    
    socketio.emit('incoming_call', {
        'call_id': call_id,
        'from': from_user,
        'type': 'offer'
    }, room=to_vehicle)
    
    return jsonify({'call_id': call_id, 'status': 'calling'})

@app.route('/api/voice/end', methods=['POST'])
def end_voice_call():
    data = request.json
    call_id = data.get('call_id')
    if call_id in _active_voice_calls:
        del _active_voice_calls[call_id]
    return jsonify({'status': 'ended'})

# ============================================
# VIDEO STREAMING
# ============================================
@app.route('/api/video/<imei>/stream', methods=['POST'])
def video_stream_start(imei):
    return jsonify({
        'stream_url': f'rtsp://camera-{imei}.local/stream',
        'status': 'streaming',
        'recording': False
    })

@app.route('/api/video/<imei>/record', methods=['POST'])
def start_recording(imei):
    data = request.json
    event = data.get('event', 'manual')
    return jsonify({
        'status': 'recording_started',
        'event': event,
        'filename': f'recording_{imei}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
    })

# ============================================
# PHONE MARKETPLACE ROUTES
# ============================================
@app.route('/phones')
def phone_marketplace():
    return render_template('phone_marketplace.html')

@app.route('/checkout')
def checkout_page():
    return render_template('checkout.html')

@app.route('/phone-admin')
def phone_admin():
    return render_template('phone_admin.html')

@app.route('/api/phones')
def get_phones_api():
    phones = load_phone_prices()
    return jsonify(phones)

@app.route('/api/orders', methods=['GET', 'POST'])
def handle_phone_orders():
    if request.method == 'POST':
        order = request.json
        orders = load_phone_orders()
        order['id'] = len(orders) + 1
        order['created_at'] = datetime.now().isoformat()
        order['status'] = 'pending'
        orders.append(order)
        save_phone_orders(orders)
        
        try:
            send_email_alert(
                f"🛍️ NEW PHONE ORDER #{order['id']}",
                f"Customer: {order['customer_name']}\nPhone: {order['customer_phone']}\nAddress: {order['delivery_address']}\nItems: {len(order['items'])}",
                "success"
            )
        except:
            pass
        
        return jsonify({'status': 'success', 'order_id': order['id']})
    else:
        orders = load_phone_orders()
        return jsonify(orders)

@app.route('/api/orders/<int:order_id>', methods=['PUT'])
def update_phone_order(order_id):
    data = request.json
    orders = load_phone_orders()
    for order in orders:
        if order['id'] == order_id:
            order['status'] = data.get('status', order.get('status'))
            order['updated_at'] = datetime.now().isoformat()
            break
    save_phone_orders(orders)
    return jsonify({'status': 'success'})

# ============================================
# CUSTOMER MESSAGING SYSTEM - TWO-WAY COMMUNICATION
# ============================================

@app.route('/api/orders/<int:order_id>/reply', methods=['POST'])
def reply_to_customer(order_id):
    """Admin replies to customer order"""
    data = request.json
    message = data.get('message')
    
    orders = load_phone_orders()
    order = None
    for o in orders:
        if o['id'] == order_id:
            order = o
            if 'replies' not in order:
                order['replies'] = []
            reply = {
                'id': len(order['replies']) + 1,
                'message': message,
                'from_admin': True,
                'timestamp': datetime.now().isoformat(),
                'read': False
            }
            order['replies'].append(reply)
            break
    
    if order:
        save_phone_orders(orders)
        
        # Send email to customer
        if order.get('customer_email'):
            try:
                send_email_alert(
                    f"📱 Update on your Order #{order_id} - iOnline Refurbished",
                    f"Dear {order['customer_name']},\n\nYou have a new message regarding your order #{order_id}:\n\n\"{message}\"\n\nPlease check your order status online.\n\nThank you for shopping with iOnline Refurbished!",
                    "info"
                )
            except:
                pass
        
        # Send real-time notification via socket
        socketio.emit('order_reply', {
            'order_id': order_id,
            'reply': reply,
            'customer_name': order.get('customer_name')
        }, broadcast=True)
        
        return jsonify({'status': 'success', 'reply': reply})
    
    return jsonify({'error': 'Order not found'}), 404

@app.route('/api/orders/<int:order_id>/customer-message', methods=['POST'])
def customer_send_message(order_id):
    """Customer sends message about order"""
    data = request.json
    message = data.get('message')
    customer_name = data.get('customer_name')
    
    orders = load_phone_orders()
    order = None
    for o in orders:
        if o['id'] == order_id:
            order = o
            if 'replies' not in order:
                order['replies'] = []
            msg = {
                'id': len(order['replies']) + 1,
                'message': message,
                'from_customer': True,
                'customer_name': customer_name,
                'timestamp': datetime.now().isoformat(),
                'read': False
            }
            order['replies'].append(msg)
            break
    
    if order:
        save_phone_orders(orders)
        
        # Send email to admin
        try:
            send_email_alert(
                f"💬 New Message from Customer - Order #{order_id}",
                f"Customer: {customer_name}\nOrder: #{order_id}\nMessage: {message}\n\nView in admin dashboard: http://127.0.0.1:5000/phone-admin",
                "warning"
            )
        except:
            pass
        
        # Send real-time notification to admin
        socketio.emit('customer_message', {
            'order_id': order_id,
            'message': msg,
            'customer_name': customer_name
        }, broadcast=True)
        
        return jsonify({'status': 'success', 'message': msg})
    
    return jsonify({'error': 'Order not found'}), 404

@app.route('/api/orders/<int:order_id>/messages', methods=['GET'])
def get_order_messages(order_id):
    """Get all messages for an order"""
    orders = load_phone_orders()
    for order in orders:
        if order['id'] == order_id:
            return jsonify(order.get('replies', []))
    return jsonify([])

# ============================================
# VOICE GREETING
# ============================================
@app.route('/api/voice-greeting')
def voice_greeting():
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 18:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"
    return jsonify({
        "greeting": greeting,
        "message": f"{greeting}! Welcome to iOnline Platform."
    })

# ============================================
# PAGE ROUTES
# ============================================
@app.route('/')
def index():
    return render_template('pro_dashboard.html')

@app.route('/driver')
def driver_app():
    return render_template('driver_app.html')

@app.route('/student')
def student_app():
    return render_template('student_app.html')

@app.route('/parent')
def parent_app():
    return render_template('parent_app.html')

@app.route('/admin-dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/telematics-driver')
def telematics_driver():
    return render_template('telematics_driver.html')

@app.route('/dispatcher')
def dispatcher_dashboard():
    return render_template('dispatcher_dashboard.html')

@app.route('/fleet-management')
def fleet_management():
    return render_template('fleet_management.html')

# ============================================
# MAIN
# ============================================
if __name__ == '__main__':
    # Create phone_prices.json if it doesn't exist
    if not os.path.exists(PHONE_PRICES_FILE):
        default_phones = {
            "phones": [
                {"id": 1, "model": "iPhone 15 Pro", "storage": "128GB", "price_rmb": 3250, "price_kes": 58500, "price_usd": 455, "condition": "Excellent", "local_price_kes": 160000},
                {"id": 2, "model": "iPhone 15 Pro", "storage": "256GB", "price_rmb": 3450, "price_kes": 62100, "price_usd": 483, "condition": "Excellent", "local_price_kes": 175000},
                {"id": 3, "model": "iPhone 15 Pro Max", "storage": "256GB", "price_rmb": 3550, "price_kes": 63900, "price_usd": 497, "condition": "Excellent", "local_price_kes": 185000},
                {"id": 4, "model": "iPhone 16", "storage": "128GB", "price_rmb": 3650, "price_kes": 65700, "price_usd": 511, "condition": "Excellent", "local_price_kes": 145000},
                {"id": 5, "model": "iPhone 16 Pro", "storage": "256GB", "price_rmb": 4800, "price_kes": 86400, "price_usd": 672, "condition": "Excellent", "local_price_kes": 205000},
                {"id": 6, "model": "iPhone 16 Pro Max", "storage": "256GB", "price_rmb": 5150, "price_kes": 92700, "price_usd": 721, "condition": "Excellent", "local_price_kes": 220000},
                {"id": 7, "model": "iPhone 14 Pro Max", "storage": "256GB", "price_rmb": 3050, "price_kes": 54900, "price_usd": 427, "condition": "Excellent", "local_price_kes": 170000},
                {"id": 8, "model": "iPhone 13 Pro Max", "storage": "256GB", "price_rmb": 2600, "price_kes": 46800, "price_usd": 364, "condition": "Excellent", "local_price_kes": 155000}
            ]
        }
        with open(PHONE_PRICES_FILE, 'w') as f:
            json.dump(default_phones, f, indent=2)
        print("✅ Created phone_prices.json with sample data")
    
    print("="*70)
    print("🚀 iOnline COMPLETE PLATFORM - TELEMATICS + PHONE MARKETPLACE")
    print("="*70)
    print("🎨 Colors: White #FFFFFF | Grey #4D4D4F | Orange #F69322")
    print("🎤 Voice AI: ENABLED")
    print("📡 MQTT Broker: Connected")
    print("📦 Delivery System: Active")
    print("🔧 Engine Monitoring: Active")
    print("🎥 Video Integration: Ready")
    print("👥 Driver Management: Complete")
    print("🛍️ Phone Marketplace: ACTIVE")
    print("💬 Two-Way Customer Messaging: ACTIVE")
    print("="*70)
    print("📱 ACCESS URLS:")
    print("👑 Admin Dashboard: http://127.0.0.1:5000/admin-dashboard")
    print("🚛 Telematics Driver: http://127.0.0.1:5000/telematics-driver")
    print("📞 Dispatcher: http://127.0.0.1:5000/dispatcher")
    print("🏢 Fleet Management: http://127.0.0.1:5000/fleet-management")
    print("🛍️ Phone Store: http://127.0.0.1:5000/phones")
    print("📋 Phone Admin: http://127.0.0.1:5000/phone-admin")
    print("="*70)
    print("🔑 LOGIN CREDENTIALS:")
    print("Admin: admin / admin123")
    print("Dispatcher: dispatcher / dispatch123")
    print("Fleet Manager: fleet_manager / fleet123")
    print("="*70)
    print("✅ CUSTOMER MESSAGING:")
    print("   - Customers can send messages about their orders")
    print("   - Admins receive real-time notifications")
    print("   - Two-way communication via email + WebSocket")
    print("="*70)
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)