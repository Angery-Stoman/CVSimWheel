# CV-Drive: Virtual Steering Wheel

## Highlights

*  **Zero-Latency Response:** One Euro Filter kinematics eliminate input lag and micro-jitter.
*  **Magnetic Center:** Custom virtual steering with a smooth cubic-easing deadzone.
*  **Live Telemetry:**  Flask backend with sub-millisecond SSE updates to a web dashboard.
*  **Hot-Swappable Profiles:** Save and load custom tuning setups.
*  **Accessible:** Play racing simulators using just a standard webcam (and your own controller).

## Overview

CV-Drive is a computer vision application that translates real-time webcam hand tracking into gamepad inputs for racing simulators. Computer vision application that translates real-time webcam hand tracking into gamepad inputs for racing simulators. Developed with the goal of eliminating input lag and optical micro-jitter, the system aims to provide a responsive, tactile driving experience without the need of physical hardware.

## Usage instructions

Launch the application from your terminal to boot the CV engine and local web server:

```

python wheel.py

```

The script will automatically open the telemetry dashboard in your default browser at `http://127.0.0.1:5000`. 

Simply position your hands in front of the camera as if holding a steering wheel. If your physical center doesn't match the virtual center, hit **Calibrate Zero** on the dashboard.

## Installation instructions

**Requirements:** 
* Python 3.8+ 
* Windows OS (required for Xbox 360 controller emulation)
* A standard webcam with decent room lighting

Install the required dependencies using pip:

```

pip install opencv-python mediapipe vgamepad flask

```

*(Note: The `vgamepad` library relies on the ViGEmBus driver. If the controller does not emulate correctly on the first run, install the ViGEmBus driver manually from the [ViGEm GitHub project](https://github.com/nefarius/vigembus)).*
