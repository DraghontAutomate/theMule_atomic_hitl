# theMule_atomic_hitl
Human-in-the-Loop for Close Guidance

## Running Locally

This application is built using Python and PyQt5 for the graphical interface.

### Dependencies

**1. Python:**
   - Ensure you have Python 3.6+ installed.

**2. System Dependencies (for Linux):**
   - If you are running on a Linux system (especially headless or in some containerized environments), you will need to install X11 client libraries and Xvfb (X Virtual FrameBuffer) for the application to run. The specific packages can vary by distribution, but for Debian/Ubuntu-based systems, you can install them with:
     ```bash
     sudo apt-get update
     sudo apt-get install -y xvfb libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xfixes0 libxcb-xinerama0 libx11-xcb1 \
     libxcb-randr0-dev libxcb-xtest0-dev libxcb-xinerama0-dev libxcb-shape0-dev libxcb-xkb-dev libxkbcommon-x11-dev libx11-xcb-dev libxcb-cursor-dev libxcb-util0-dev libxcb-keysyms1-dev libxcb-icccm4-dev libxcb-image0-dev libxcb-render-util0-dev libxcb-xfixes0-dev libxcb1-dev
     ```
   - For other operating systems (Windows, macOS), these are typically handled by the Qt installation itself, but ensure your X11 environment (like XQuartz on macOS) is set up if needed.

**3. Python Packages:**
   - Install the required Python packages using the provided `requirements.txt` file:
     ```bash
     pip install -r requirements.txt
     ```
     This will install `PyQt5` and `PyQtWebEngine`.

### Launching the Example

Once dependencies are installed:

- **On a desktop environment (Windows, macOS, Linux with a display server):**
  Navigate to the repository root and run:
  ```bash
  python examples/run_tool.py
  ```

- **On a headless Linux environment (or if you encounter Qt platform errors):**
  You can use `xvfb-run` to provide a virtual display:
  ```bash
  xvfb-run -a python examples/run_tool.py
  ```

This will launch the example application using the configuration and data found in the `examples/` directory. The application window should appear.
The Monaco editor component used in the frontend is loaded from a CDN, so an active internet connection is required when running the application.
