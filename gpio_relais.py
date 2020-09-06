import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

GPIO.setup(7, GPIO.OUT)
GPIO.setwarnings(False)

print("on")
GPIO.output(7,GPIO.LOW)
time.sleep(0.5)
print("off")
GPIO.output(7,GPIO.HIGH)

print("Done")
