import cv2
import mediapipe as mp
import math
import vgamepad as vg
import time
import threading
import logging
import json
import os
import webbrowser
from flask import Flask, render_template, request, jsonify, Response

CONFIG_FILE = "steering_config.json"

profiles_db = {
    "active_profile": "Default Rally",
    "profiles": {
        "Default Rally": {
            "static_smooth": 40,
            "dynamic_response": 50,
            "max_angle": 55,
            "deadzone": 5,
            "linearity": 100,
            "center_offset": 0.0
        }
    }
}

global_static_smooth = 40
global_dynamic_response = 50
global_max_angle = 55
global_deadzone = 5
global_linearity = 100
global_center_offset = 0.0

current_steering = 50.0 
is_calibrating = False
calibration_frames = []

def load_config():
    """loads JSON into global variables."""
    global global_static_smooth, global_dynamic_response, global_max_angle, global_deadzone, global_linearity, global_center_offset, profiles_db
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                
                if "profiles" in data:
                    profiles_db = data
                else:
                    profiles_db["profiles"]["Default Rally"] = {
                        "static_smooth": data.get("alpha", 40), 
                        "dynamic_response": 50,
                        "max_angle": data.get("max_angle", 55),
                        "deadzone": data.get("deadzone", 5),
                        "linearity": data.get("linearity", 100),
                        "center_offset": data.get("center_offset", 0.0)
                    }
                    profiles_db["active_profile"] = "Default Rally"

            active = profiles_db.get("active_profile", "Default Rally")
            if active not in profiles_db["profiles"]:
                active = list(profiles_db["profiles"].keys())[0]
                
            prof = profiles_db["profiles"][active]
            global_static_smooth = prof.get("static_smooth", 40)
            if "alpha" in prof and "static_smooth" not in prof:
                global_static_smooth = prof["alpha"]
                
            global_dynamic_response = prof.get("dynamic_response", 50)
            global_max_angle = prof.get("max_angle", 55)
            global_deadzone = prof.get("deadzone", 5)
            global_linearity = prof.get("linearity", 100)
            global_center_offset = prof.get("center_offset", 0.0)
        except Exception:
            pass

def save_config():
    """for persisting user adjustments."""
    try:
        active = profiles_db["active_profile"]
        profiles_db["profiles"][active] = {
            "static_smooth": global_static_smooth,
            "dynamic_response": global_dynamic_response,
            "max_angle": global_max_angle,
            "deadzone": global_deadzone,
            "linearity": global_linearity,
            "center_offset": global_center_offset
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(profiles_db, f)
    except Exception:
        pass

load_config()

# one euro filter smoothing (pretty neat)
class OneEuroFilter:
    def __init__(self, t0, x0, dx0=0.0, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff) # static smoothing (small movements)
        self.beta = float(beta)             # dynamic response (flicks)
        self.d_cutoff = float(d_cutoff)
        self.x_prev = float(x0)
        self.dx_prev = float(dx0)
        self.t_prev = float(t0)

    def alpha(self, t_e, cutoff):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / t_e)

    def __call__(self, t, x):
        t_e = t - self.t_prev
        if t_e <= 0.0: return x
        
        # firstly, we estimate the velocity (dx_hat)
        a_d = self.alpha(t_e, self.d_cutoff)
        dx = (x - self.x_prev) / t_e
        dx_hat = a_d * dx + (1.0 - a_d) * self.dx_prev
        
        # then calculate the cutoff based on velocity
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        
        # aaand apply the filter on our raw input
        a = self.alpha(t_e, cutoff)
        x_hat = a * x + (1.0 - a) * self.x_prev
        
        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        
        return x_hat

# flask web shenanigans

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def index():
    return render_template('index.html', 
                           static_smooth=global_static_smooth,
                           dynamic_response=global_dynamic_response,
                           max_angle=global_max_angle, 
                           deadzone=global_deadzone, 
                           linearity=global_linearity,
                           profiles=list(profiles_db["profiles"].keys()),
                           active_profile=profiles_db["active_profile"])

@app.route('/update', methods=['POST'])
def update():
    """for receiving slider changes from the web UI."""
    global global_static_smooth, global_dynamic_response, global_max_angle, global_deadzone, global_linearity
    data = request.json
    if 'static_smooth' in data: global_static_smooth = int(data['static_smooth'])
    if 'dynamic_response' in data: global_dynamic_response = int(data['dynamic_response'])
    if 'max_angle' in data: global_max_angle = int(data['max_angle'])
    if 'deadzone' in data: global_deadzone = int(data['deadzone'])
    if 'linearity' in data: global_linearity = int(data['linearity'])
    save_config()
    return jsonify(success=True)

@app.route('/save_profile', methods=['POST'])
def save_profile():
    global profiles_db
    name = request.json.get("name")
    if name:
        profiles_db["active_profile"] = name
        save_config()
    return jsonify(success=True)

@app.route('/load_profile', methods=['POST'])
def load_profile():
    global profiles_db
    name = request.json.get("name")
    if name and name in profiles_db["profiles"]:
        profiles_db["active_profile"] = name
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(profiles_db, f)
        except Exception:
            pass
        load_config()
    return jsonify(success=True)

@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    global profiles_db
    name = request.json.get("name")
    if name and name in profiles_db["profiles"] and len(profiles_db["profiles"]) > 1:
        del profiles_db["profiles"][name]
        if profiles_db["active_profile"] == name:
            profiles_db["active_profile"] = list(profiles_db["profiles"].keys())[0]
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(profiles_db, f)
        except Exception:
            pass
        load_config()
    return jsonify(success=True)

@app.route('/calibrate', methods=['POST'])
def calibrate():
    """calibration loop."""
    global is_calibrating, calibration_frames
    is_calibrating = True
    calibration_frames = []
    return jsonify(success=True)

@app.route('/stream')
def stream():
    """server-sent event for the steering gauge on the web UI."""
    def generate():
        while True:
            yield f"data: {current_steering}\n\n"
            time.sleep(0.016) # hopefully we pull 60fps from the camera
    return Response(generate(), mimetype='text/event-stream')

def run_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)

# input and output handling
class CameraCapture:
    """runs the webcam on a dedicated daemon thread in order to prevent I/O blocking in the main loop."""
    def __init__(self, src=2):
        self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        self.success, self.frame = self.cap.read()
        self.stopped = False
        threading.Thread(target=self.update, daemon=True).start()

    def update(self):
        while not self.stopped:
            if not self.cap.isOpened(): break
            self.success, self.frame = self.cap.read()

    def read(self):
        return self.success, self.frame.copy() if self.success else None

    def release(self):
        self.stopped = True
        self.cap.release()

# physics calculations
def calculate_steering(raw_angle, max_angle, deadzone, center_offset, linearity):
    adjusted_angle = raw_angle - center_offset
    abs_angle = abs(adjusted_angle)
    
    # deadzone
    if abs_angle <= deadzone: 
        return 50.0
        
    excess = abs_angle - deadzone
    effective_max = max(1.0, max_angle - deadzone)
    
    # magnetic Center : 
    # uses an ease-in-out curve to smoothly blend the deadzone into the active steering range to prevents sudden snap-oversteer.
    transition_range = 8.0 
    if excess < transition_range:
        blend = excess / transition_range
        ease = blend * blend * (3.0 - 2.0 * blend) 
        excess = ease * transition_range
        
    clamped_excess = min(excess, effective_max)
    
    # gamma Linearity:
    # curves the output so the center is less sensitive than the edges, which allows you to make micro-adjustments easier.
    gamma = 1.0 + ((100 - linearity) * 0.02)
    normalized = clamped_excess / effective_max
    curved = math.pow(normalized, gamma)
    
    final_angle = curved * effective_max
    if adjusted_angle < 0: 
        final_angle = -final_angle
    
    # map final physics to a 0.0 - 100.0 percentage for the dashboard and emulator
    steering_percentage = ((final_angle + effective_max) / (2 * effective_max)) * 100
    return max(0.0, min(100.0, 100.0 - steering_percentage))

def main():
    global current_steering, is_calibrating, calibration_frames, global_center_offset
    
    # boot the UI server on a parallel thread
    threading.Thread(target=run_server, daemon=True).start()
    webbrowser.open("http://127.0.0.1:5000")
    
    # initialize the virtual Xbox 360 controller
    gamepad = vg.VX360Gamepad()
    
    # initialize Google MediaPipe Hand Tracking
    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    hands = mp_hands.Hands(model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5, max_num_hands=2)

    cam = CameraCapture(src=2)
    window_name = "Virtual Steering Wheel"
    cv2.namedWindow(window_name)

    one_euro = OneEuroFilter(time.time(), 50.0)
    pTime = 0
    label_mapping = None

    print("Driver active. Server running at http://localhost:5000")
    print("Press 'q' in the camera window to quit.")

    while True:
        success, frame = cam.read()
        if not success or frame is None:
            continue
            
        h, w, _ = frame.shape
        cTime = time.time()
        
        # map UI sliders directly to the one euro filter parameters
        one_euro.min_cutoff = 10.0 / max(1, global_static_smooth) 
        one_euro.beta = global_dynamic_response / 1000.0

        max_angle = global_max_angle
        deadzone = global_deadzone
        linearity = global_linearity

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        if results.multi_hand_landmarks and len(results.multi_hand_landmarks) == 2:
            hand_dict = {}
            for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # extract Hand classification (Left/Right) and the middle finger knuckle (Landmark 9)
                label = results.multi_handedness[i].classification[0].label
                lm = hand_landmarks.landmark[9]
                cx, cy = int(lm.x * w), int(lm.y * h)
                hand_dict[label] = (cx, cy)
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            if "Left" in hand_dict and "Right" in hand_dict:
                # this locks the hand mapping, so that your hand tracking doesn't switch if you cross arms
                if label_mapping is None:
                    labels = list(hand_dict.keys())
                    label_A, label_B = labels[0], labels[1]
                    if hand_dict[label_A][0] > hand_dict[label_B][0]:
                        label_mapping = {"physical_left": label_A, "physical_right": label_B}
                    else:
                        label_mapping = {"physical_left": label_B, "physical_right": label_A}

                left_hand = hand_dict[label_mapping["physical_left"]]
                right_hand = hand_dict[label_mapping["physical_right"]]

                # trigonometry (atan2) to calculate the exact angle between both hands
                dx = left_hand[0] - right_hand[0]
                dy = left_hand[1] - right_hand[1]
                raw_angle = math.degrees(math.atan2(dy, dx))

                if is_calibrating:
                    calibration_frames.append(raw_angle)
                    if len(calibration_frames) >= 30: 
                        global_center_offset = sum(calibration_frames) / len(calibration_frames)
                        is_calibrating = False
                        save_config()

                # process the physical input through the virtual rack physics and the kinematic filter
                raw_steering = calculate_steering(raw_angle, max_angle, deadzone, global_center_offset, linearity)
                smoothed_steering = one_euro(cTime, raw_steering)

                # emulate the physical controller stick (-32768 to 32767 range)
                joystick_val = int((smoothed_steering / 100.0) * 65535 - 32768)
                gamepad.left_joystick(x_value=joystick_val, y_value=0)
                gamepad.update()
                
                current_steering = smoothed_steering

                # telemetry overlays on the OpenCV Window
                cv2.line(frame, left_hand, right_hand, (255, 0, 255), 3)
                cv2.circle(frame, left_hand, 8, (255, 0, 0), -1)
                cv2.circle(frame, right_hand, 8, (0, 0, 255), -1)
                
                gauge_x = int(10 + (smoothed_steering / 100.0) * 400)
                cv2.rectangle(frame, (10, 50), (410, 80), (255, 255, 255), 2)
                cv2.line(frame, (210, 40), (210, 90), (255, 255, 255), 2)
                cv2.circle(frame, (gauge_x, 65), 10, (0, 255, 0), -1)
        else:
            label_mapping = None
            gamepad.left_joystick(x_value=0, y_value=0)
            gamepad.update()
            
            _ = one_euro(cTime, 50.0)
            current_steering = 50.0

        fps = 1 / (cTime - pTime)
        pTime = cTime
        cv2.putText(frame, f"FPS: {int(fps)}", (500, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

        cv2.imshow(window_name, frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cam.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()