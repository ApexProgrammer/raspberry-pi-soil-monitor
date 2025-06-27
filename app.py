from flask import Flask, render_template, jsonify
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import threading
import json
from datetime import datetime
from collections import deque
import pytz

app = Flask(__name__)

# Timezone configuration
CENTRAL_TZ = pytz.timezone('US/Central')

def get_central_time():
    """Get current time in Central timezone"""
    return datetime.now(CENTRAL_TZ)

def format_central_time(dt_format='%Y-%m-%d %H:%M:%S %Z'):
    """Format current Central time as string"""
    return get_central_time().strftime(dt_format)

# Global variables to store sensor data
sensor_data = {
    'voltage': 0.0,
    'moisture_percentage': 0.0,
    'status': 'Dry',
    'last_updated': None,
    'readings_history': deque(maxlen=30)  # Reduced from 50 to 30 readings for better performance
}

# Sensor configuration
try:
    # Create the I2C bus
    i2c = busio.I2C(board.SCL, board.SDA)
    
    # Create the ADS object
    ads = ADS.ADS1115(i2c)
    
    # Create a single-ended input on channel 0
    chan = AnalogIn(ads, ADS.P0)
    sensor_available = True
except Exception as e:
    print(f"Sensor initialization failed: {e}")
    sensor_available = False

def voltage_to_moisture(voltage):
    """Convert voltage reading to moisture percentage
    
    Based on capacitive soil moisture sensor specifications:
    - Dry Soil: ~3.0V (0% moisture)
    - Moist Soil: ~1.5V (100% moisture)
    - Higher voltage = drier soil
    - Lower voltage = wetter soil
    """
    # Calibration values for capacitive soil moisture sensor
    dry_voltage = 3.0   # Voltage reading in completely dry soil
    wet_voltage = 1.5   # Voltage reading in very wet soil
    
    # Clamp voltage to expected range
    voltage = max(wet_voltage, min(dry_voltage, voltage))
    
    if voltage >= dry_voltage:
        return 0.0  # Completely dry
    elif voltage <= wet_voltage:
        return 100.0  # Completely wet
    else:
        # Linear interpolation: higher voltage = lower moisture %
        percentage = ((dry_voltage - voltage) / (dry_voltage - wet_voltage)) * 100
        return round(max(0.0, min(100.0, percentage)), 1)

def get_moisture_status(percentage):
    """Get moisture status based on percentage
    
    Soil moisture categories:
    - Dry: 0-25% (needs watering)
    - Moist: 25-65% (optimal range)
    - Wet: 65-100% (may be overwatered)
    """
    if percentage < 25:
        return "Dry"
    elif percentage < 65:
        return "Moist"
    else:
        return "Wet"

def read_sensor_data():
    """Background thread function to continuously read sensor data"""
    global sensor_data
    
    while True:
        try:
            if sensor_available:
                voltage = chan.voltage
                moisture_percentage = voltage_to_moisture(voltage)
                status = get_moisture_status(moisture_percentage)
                
                # Update global sensor data
                sensor_data['voltage'] = voltage
                sensor_data['moisture_percentage'] = moisture_percentage
                sensor_data['status'] = status
                sensor_data['last_updated'] = format_central_time('%Y-%m-%d %H:%M:%S %Z')
                
                # Add to history for charting
                sensor_data['readings_history'].append({
                    'timestamp': format_central_time('%H:%M:%S'),
                    'moisture': moisture_percentage,
                    'voltage': voltage
                })
            else:
                # Simulate data if sensor is not available (for testing)
                # Use realistic voltage range for capacitive soil sensor
                import random
                voltage = random.uniform(1.5, 3.0)  # Match real sensor range
                moisture_percentage = voltage_to_moisture(voltage)
                status = get_moisture_status(moisture_percentage)
                
                sensor_data['voltage'] = voltage
                sensor_data['moisture_percentage'] = moisture_percentage
                sensor_data['status'] = status
                sensor_data['last_updated'] = format_central_time('%Y-%m-%d %H:%M:%S %Z')
                
                sensor_data['readings_history'].append({
                    'timestamp': format_central_time('%H:%M:%S'),
                    'moisture': moisture_percentage,
                    'voltage': voltage
                })
            
        except Exception as e:
            print(f"Error reading sensor: {e}")
        
        time.sleep(3600)  # Read every hour (3600 seconds)

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/sensor-data')
def get_sensor_data():
    """API endpoint to get current sensor data"""
    # Create a copy of sensor_data without the deque object
    response_data = {
        'voltage': sensor_data['voltage'],
        'moisture_percentage': sensor_data['moisture_percentage'],
        'status': sensor_data['status'],
        'last_updated': sensor_data['last_updated']
    }
    return jsonify(response_data)

@app.route('/api/history')
def get_history():
    """API endpoint to get sensor history for charts"""
    return jsonify(list(sensor_data['readings_history']))

if __name__ == '__main__':
    # Start the sensor reading thread
    sensor_thread = threading.Thread(target=read_sensor_data, daemon=True)
    sensor_thread.start()
    
    print("Starting Soil Moisture Monitor...")
    print("Access the dashboard at: http://localhost:5000")
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
