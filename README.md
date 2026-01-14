# iPerf3 GUI (NetTestTool)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)]()

A lightweight, standalone Windows GUI wrapper for the popular network performance measurement tool `iperf3`. 

Looking for a simple way to test network bandwidth without memorizing command-line arguments? This tool provides a clean interface for both TCP and UDP testing, real-time plotting, and log recording.

![App Screenshot](https://via.placeholder.com/800x500.png?text=iPerf3+GUI+Screenshot+Placeholder)
*(Replace this link with a real screenshot of your app)*

## ✨ Features

*   **Zero Dependencies**: Packaged as a standalone folder; no Python installation required for end-users.
*   **Protocol Support**: Full support for TCP and UDP bandwidth testing.
*   **Real-time Metrics**: Live display of bandwidth, jitter, and packet loss.
*   **Breakpoint Testing**: Optional sampling mode to record bandwidth at specific intervals.
*   **Console Hiding**: Runs silently in the background without annoying popup command windows.
*   **Log Export**: Easily save test logs and breakpoint data to text files.

## 🚀 Getting Started

### Prerequisites

*   Windows OS (tested on Windows 10/11)
*   [iPerf3 for Windows](https://iperf.fr/iperf-download.php) binaries (`iperf3.exe` and `cygwin1.dll`)

### Running from Source

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/iperf3-action.git
    cd iperf3-action
    ```

2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Download iPerf3 binaries**
    *   Download the latest Windows build from [iperf.fr](https://iperf.fr/iperf-download.php).
    *   Extract `iperf3.exe` and `cygwin1.dll` into the project root folder.

4.  **Run the application**
    ```bash
    python main.py
    ```

## 📦 Building Executable

To compile the application into a standalone Windows executable:

1.  **Install PyInstaller**
    ```bash
    pip install pyinstaller
    ```

2.  **Build**
    Use the included build command to generate a clean, windowed application:
    ```bash
    pyinstaller --name "NetTestTool" --onedir --windowed --noconfirm --clean --noupx main.py
    ```

3.  **Finalize**
    *   Navigate to the `dist/NetTestTool` folder.
    *   **Crucial Step**: Manually copy `iperf3.exe` and `cygwin1.dll` into this folder.
    *   Run `NetTestTool.exe`.

## 🛠 Usage

1.  **Server IP**: Enter the IP address of the remote iPerf3 server (e.g., `192.168.1.100`).
2.  **Mode**: Select **TCP** for standard bandwidth or **UDP** for jitter/packet loss testing.
3.  **Actions**:
    *   Click **Start Test** to begin.
    *   Use **Breakpoint Sampling** if you need to capture instantaneous speed snapshots every X seconds.
4.  **Logs**: Click **Save Main Log** to export the entire session output.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## 🙏 Acknowledgments

*   [iPerf3](https://github.com/esnet/iperf) - The underlying network tool.
*   Python Tkinter - For the GUI framework.