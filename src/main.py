# This Python file uses the following encoding: utf-8
import sys
# from PySide6.QtWidgets import QApplication
import json
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from hijri_converter import convert
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QLabel, QFrame, QGridLayout, QSystemTrayIcon, QMenu, QAction)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtMultimedia import QSound

class DigitalDisplay(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
        QLabel {
            background-color: black;
            color: #ff4444;
            border: 1px solid #8b0000;
            border-radius: 5px;
            padding: 1px;
            font-family: 'Digital-7', 'Courier New';
        }
        """)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Digital-7", 30))
        self.setMinimumHeight(30)

class PrayerNameLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
        QLabel {
            color: #4a4a4a;
            font-weight: bold;
            font-size: 16px;
            text-align: center;
        }
        """)
        self.setAlignment(Qt.AlignCenter)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Prayer Times Display")
        self.setStyleSheet("""
        QMainWindow {
            background-color: #f4e4bc;
        }
        """)

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # Create ornate frame
        frame = QFrame()
        frame.setStyleSheet("""
        QFrame {
            background-color: #f8f0e3;
            border: 3px solid #8b4513;
            border-radius: 15px;
            margin: 5px;
        }
        """)
        self.alarm_sound = QSound("src/assets/alarm.wav")

        # Main layout
        main_layout = QVBoxLayout(main_widget)
        frame_layout = QGridLayout(frame)
        main_layout.addWidget(frame)

        # Date and Time Display
        self.date_display = DigitalDisplay()
        self.time_display = DigitalDisplay()
        self.temp_display = DigitalDisplay()
        self.remainder_display = DigitalDisplay()

        # Prayer time displays
        self.prayer_displays = {}
        prayer_names = {
            "الفجر": "Fajr",
            "الشروق": "Sunrise",
            "الظهر": "Dhuhr",
            "العصر": "Asr",
            "المغرب": "Maghrib",
            "العشاء": "Isha"
        }

        # Add Hijri date and time at the top
        frame_layout.addWidget(self.date_display, 0, 0, 1, 3)
        frame_layout.addWidget(self.time_display, 1, 0, 1, 3)

        # Add prayer times
        row = 2
        for arabic, english in prayer_names.items():
            name_label_ar = PrayerNameLabel(f"{arabic}")
            time_display = DigitalDisplay()
            self.prayer_displays[english] = time_display

            frame_layout.addWidget(time_display, row, 0, 1, 2)
            frame_layout.addWidget(name_label_ar, row, 2)

            row += 1

        # Add temperature and remainder time at bottom
        frame_layout.addWidget(self.remainder_display, row, 0, 1, 2)
        frame_layout.addWidget(self.temp_display, row, 2)

        # Set window size
        # self.setBaseSize(400, 700)
        self.setFixedSize(400, 700)

        # Start timers
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # Update every second for time display

        # Timer for alternating date display
        self.date_switch_timer = QTimer()
        self.date_switch_timer.timeout.connect(self.toggle_date_display)
        self.date_switch_timer.start(10000)  # Switch every 10 seconds

        # Initial update
        self.show_hijri = True  # Flag for toggling date display

        # Arabic month names mapping for Gregorian
        self.arabic_months = {
            1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
            5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
            9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
        }

        # Arabic month names mapping for Hijri
        self.arabic_hijri_months = {
            1: "محرم", 2: "صفر", 3: "ربيع الأول", 4: "ربيع الآخر",
            5: "جمادى الأولى", 6: "جمادى الآخرة", 7: "رجب", 8: "شعبان",
            9: "رمضان", 10: "شوال", 11: "ذو القعدة", 12: "ذو الحجة"
        }

        # Initialize the tray icon and menu before updating prayer times
        self.create_tray_icon()

        if self.get_next_prayer(datetime.now()) is True:
            self.trigger_alarm()

        self.update_display()  # Call update_display after initializing everything
        self.update_prayer_times()

    def closeEvent(self, event):
            """Override close event to hide the window instead of closing it."""
            event.ignore()  # Ignore the close event
            self.hide()  # Hide the main window
            # self.tray_icon.showMessage("Prayer Times Application", "The application is still running in the background.", QSystemTrayIcon.Information)

    def create_tray_icon(self):
        # Create the tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("assets/icon.png"))  # Use your icon path here
        self.tray_icon.setToolTip("Prayer Times Application")

        # Create the context menu for the tray icon
        self.tray_menu = QMenu()

        # Add toggle visibility action
        toggle_action = QAction("Show/Hide", self)
        toggle_action.triggered.connect(self.toggle_visibility)
        self.tray_menu.addAction(toggle_action)

        # Add Exit action to the menu
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(QApplication.instance().quit)
        self.tray_menu.addAction(exit_action)

        # Set menu to tray icon and show it
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

        # Connect the icon click to toggle visibility
        self.tray_icon.activated.connect(self.tray_icon_click)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()  # Hide the window
            self.tray_icon.setToolTip("Prayer Times Application - Click to Show")
        else:
            self.show()  # Show the window
            self.tray_icon.setToolTip("Prayer Times Application - Click to Hide")

    def tray_icon_click(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_visibility()  # Toggle visibility on icon click

    def update_prayer_summary(self):
        # Clear old summary actions
        self.tray_menu.clear()

        # Add new actions for each prayer time
        for prayer, display in self.prayer_displays.items():
            prayer_time_text = display.text().strip()
            action = QAction(f"{prayer}: {prayer_time_text}", self)
            action.setEnabled(False)  # Disable actions to make it read-only
            self.tray_menu.addAction(action)

        # Add a separator and the Exit action again
        self.tray_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(QApplication.instance().quit)
        self.tray_menu.addAction(exit_action)

    # def trigger_alarm(self):
    #     self.alarm_sound.play()  # Play alarm sound

    def trigger_alarm(self):
        if not hasattr(self, 'alarm_active') or not self.alarm_active:
            self.play_athan()
            QTimer.singleShot(8000, self.stop_athan)  # Stop after 8 seconds
            self.alarm_active = False  # Reset the flag to indicate the alarm is no longer active

    def update_display(self):
        now = datetime.now()
        hijri_date = convert.Gregorian(now.year, now.month, now.day).to_hijri()
        gregorian_date = (now.year, now.month, now.day)

        if self.show_hijri:
            hijri_month = self.arabic_hijri_months[hijri_date.month]
            self.date_display.setText(f"{hijri_date.day} {hijri_month} {hijri_date.year}")
        else:
            arabic_month = self.arabic_months[gregorian_date[1]]
            self.date_display.setText(f"{gregorian_date[2]} {arabic_month} {gregorian_date[0]}")

        self.time_display.setText(now.strftime("%H:%M:%S"))
        self.temp_display.setText(f"{self.get_weather()}°C")
        self.remainder_display.setFont(QFont("Digital-7", 20))
        self.remainder_display.setText(self.get_next_prayer(now))

    def toggle_date_display(self):
        self.show_hijri = not self.show_hijri
        self.update_display()

    def convert_to_24h(self, time_str):
        return datetime.strptime(time_str, '%I:%M %p').strftime('%H:%M')

    def get_prayer_times(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            prayer_times_table = soup.find('table', class_='ptm_table')
            prayer_times_row = prayer_times_table.find('tbody').find('tr')

            prayer_times = {}
            for label in ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                time_12h = prayer_times_row.find('td', {'data-label': label}).text.strip()
                time_24h = self.convert_to_24h(time_12h)
                prayer_times[label] = {'12h': time_12h, '24h': time_24h}

            return prayer_times
        except requests.RequestException:
            print('No internet connection. Loading data from the local file.')
            try:
                with open('src/data/data.json', 'r') as f:
                    data = json.load(f)
                    prayer_times = data["prayer_times"][list(data["prayer_times"].keys())[0]]
            except (FileNotFoundError, json.JSONDecodeError):
                print('Feild to Load Prayer Time, File Not Found')
                return {}

            return prayer_times

    def save_prayer_times(self, prayer_times):
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            # Try to load existing data
            with open('src/data/data.json', 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Initialize with an empty structure if the file does not exist or is invalid
            data = {"prayer_times": {}, "temperature": {}}

        # Clear the "prayer_times" dictionary and only keep today's data
        data["prayer_times"] = {today: prayer_times}

        # Write the updated data back to the file
        with open('src/data/data.json', 'w') as f:
            json.dump(data, f, indent=2)

    def update_prayer_times(self):
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            with open('src/data/data.json', 'r') as f:
                data = json.load(f)
            if today in data["prayer_times"]:
                prayer_times = data["prayer_times"][today]
            else:
                url = "https://www.urdupoint.com/islam/mostaganem-prayer-timings.html"
                prayer_times = self.get_prayer_times(url)
                self.save_prayer_times(prayer_times)

        except (FileNotFoundError, json.JSONDecodeError):
            print('Feild to Load Prayer Time, File Not Found')

        for prayer, times in prayer_times.items():
            self.prayer_displays[prayer].setText(times['24h'])

        self.update_prayer_summary()

    def get_next_prayer(self, now):
        arabic_names = {
            "Fajr": "الفجر",
            "Dhuhr": "الظهر",
            "Asr": "العصر",
            "Maghrib": "المغرب",
            "Isha": "العشاء"
        }

        current_time = now.time()
        next_prayer = None
        next_time = None

        for prayer, display in self.prayer_displays.items():
            text = display.text().strip()
            if not text:
                continue

            try:
                prayer_time = datetime.strptime(text, "%H:%M").time()
                if prayer_time > current_time:
                    if next_time is None or prayer_time < next_time:
                        next_time = prayer_time
                        next_prayer = prayer
                elif prayer_time.hour == current_time.hour and prayer_time.minute == current_time.minute:
                    next_time = prayer_time
                    next_prayer = prayer
            except ValueError:
                continue

        if next_prayer is None:
            first_prayer_text = self.prayer_displays["Fajr"].text().strip()
            if first_prayer_text:
                try:
                    next_time = datetime.strptime(first_prayer_text, "%H:%M").time()
                    next_prayer = "Fajr"
                except ValueError:
                    return "-- --"

        if next_prayer is None:
            return "-- --"

        prayer_datetime = datetime.combine(now.date(), next_time)
        if next_prayer == "Fajr" and current_time > next_time:
            prayer_datetime += timedelta(days=1)

        remaining = prayer_datetime - now

        if (remaining.seconds == 0 or
            (next_time.hour == current_time.hour and
            next_time.minute == current_time.minute)):

            if not hasattr(self, 'alarm_active'):
                self.alarm_active = True
                self.play_athan()

            if not hasattr(self, 'blink_timer'):
                self.blink_timer = QTimer()
                self.blink_timer.timeout.connect(self.toggle_text_visibility)
                self.blink_timer.start(500)
                QTimer.singleShot(5000, self.stop_blinking)

            return f"{arabic_names[next_prayer]} الآن"

        # Include seconds in the remaining time calculation
        total_seconds = remaining.total_seconds()
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{arabic_names[next_prayer]} بعد {int(hours):02}:{int(minutes):02}:{int(seconds):02}"

    def toggle_text_visibility(self):
        if not hasattr(self, 'text_visible'):
            self.text_visible = True
        self.text_visible = not self.text_visible
        if self.text_visible:
            self.remainder_display.setText(self.remainder_display.text())
        else:
            self.remainder_display.setText("")

    def stop_blinking(self):
        if hasattr(self, 'blink_timer'):
            self.blink_timer.stop()
            delattr(self, 'blink_timer')
        self.update_display()  # Ensure the correct text is displayed after blinking
        if hasattr(self, 'text_visible'):
            delattr(self, 'text_visible')

    def play_athan(self):
        try:
            self.alarm_sound.play()
            self.alarm_active = True  # Set the flag to indicate the alarm is active
        except Exception as e:
            print(f"Error playing athan: {e}")

    def stop_athan(self):
        if hasattr(self, 'alarm_sound'):
            self.alarm_sound.stop()
        if hasattr(self, 'alarm_active'):
            delattr(self, 'alarm_active')



    def get_weather(self):
        try:
            with open('src/data/data.json', 'r') as f:
                data = json.load(f)
                if "temperature" in data and "value" in data["temperature"]:
                    return int(data["temperature"]["value"])
                else:
                    return "N/A"
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"prayer_times": {}, "temperature": {}}

        city_name = "Mostaganem"
        api_key = "d10bd5d398ebda3ba67463f8e85785e5"
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                weather_data = response.json()
                temperature = weather_data['main']['temp'] - 273.15
                data["temperature"] = {
                    "last_updated": datetime.now().isoformat(),
                    "value": temperature
                }
                with open('src/data/data.json', 'w') as f:
                    json.dump(data, f, indent=2)
                return temperature
        except requests.RequestException:
            print('Feild to Load Weather, File not found')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
