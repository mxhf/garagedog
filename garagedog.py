#!/usr/bin/env python
from flask import Flask
from flask_ask import Ask, statement, convert_errors
import RPi.GPIO as GPIO
import logging
import time
from datetime import datetime
from threading import Thread

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import paho.mqtt.client as mqtt

import Adafruit_DHT

MQTT_SERVER = "192.168.2.149"

GPIO.setmode(GPIO.BCM)

GARAGE_DRIVE = 7
GARAGE_OPEN_SWITCH  = 24

app = Flask(__name__)
ask = Ask(app, '/')

logging.getLogger("flask_ask").setLevel(logging.DEBUG)

GPIO.setwarnings(False)

GPIO.setup(GARAGE_DRIVE, GPIO.OUT)
GPIO.setup(GARAGE_OPEN_SWITCH, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.output(GARAGE_DRIVE,GPIO.HIGH)

state = not GPIO.input(GARAGE_OPEN_SWITCH)
print('state of switch',state)

#PERIODICAL_CHECK_INTERVAL = 180
PERIODICAL_CHECK_INTERVAL = 10
STATE_DOOR = False
EMAIL_SENT = False
EMAIL_WARN_TIME = 900

client = None

DOOR_OPEN_TIME = time.time() 

def send_email(alert_summary, info = "", pngfiles=[]):
    global EMAIL_SENT
    
    COMMASPACE = ', '

    gmail_user = 'mxhfesp32@gmail.com'  
    gmail_password = 'Dtnc4ui8QGQh'

    sent_from = gmail_user  
    to = ['mfabricius@gmail.com']  
    subject = 'Garage Dog Alert:'  

    email_text = "Garage Dog Alert:\n{}\n".format(alert_summary)
    email_text += "{}\n".format(info)
    
    # Create the container (outer) email message.
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sent_from
    msg['To'] = COMMASPACE.join(to)
    part1 = MIMEText(email_text, 'plain')
    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    msg.attach(part1)
    
    
    # Assume we know that the image files are all in PNG format
    for file in pngfiles:
        # Open the files in binary mode.  Let the MIMEImage class automatically
        # guess the specific image type.
        fp = open(file, 'rb')
        img = MIMEImage(fp.read())
        fp.close()
        msg.attach(img)
    
    try: 
        print("send_email: Trying to send email.")
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(gmail_user, gmail_password)
        server.sendmail(sent_from, to, msg.as_string())
        server.close()

        print( 'send_email: Email sent!' )
        EMAIL_SENT = True
    except:  
        print( 'send_email: Something went wrong...' )


def periodical_check():
    global STATE_DOOR, EMAIL_SENT, EMAIL_WARN_TIME, PERIODICAL_CHECK_INTERVAL, client, DOOR_OPEN_TIME 
    while True:
      print("periodical_check: Checking")
      state = not GPIO.input(GARAGE_OPEN_SWITCH)
      print('periodical_check: state of switch',state)
      if (state == True):
          client.publish("garage/door/state","open")
          if STATE_DOOR == False:
              print("periodical_check: Detetected that the door was just opened.")
              DOOR_OPEN_TIME = time.time() 
              now  = time.time()
              deltatime = now - DOOR_OPEN_TIME
              client.publish("garage/door/open_since", int(deltatime))
              STATE_DOOR = True
          else:
              print("periodical_check: Garage door has been open for {:.1f} seconds.".format(deltatime))
              now  = time.time()
              deltatime = now - DOOR_OPEN_TIME
              client.publish("garage/door/open_since",int(deltatime))
              if deltatime > EMAIL_WARN_TIME:
                  if EMAIL_SENT == False:
                      print("periodical_check: Sending warning email.")
                      send_email("Garage door has been open for {:.1f} minutes.".format(deltatime/60.))
                  else:
                      print("periodical_check: Warning mail was already sent.")
                          
      else:
          client.publish("garage/door/state","closed")
          client.publish("garage/door/open_since","")
          STATE_DOOR = False
          EMAIL_SENT = False

      dateTimeObj = datetime.now()
      humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, 4)
      if humidity is not None and temperature is not None:
          timestampStr = dateTimeObj.strftime("%d-%b-%Y %H:%M:%S")
          print('{} Temp={:0.1f}*  Humidity={:0.1f}%'.format(timestampStr, temperature, humidity))
          client.publish("garage/time", timestampStr)
          client.publish("garage/temperature", temperature)
          client.publish("garage/humidity", humidity)
      else:
          print('Failed to get reading. Try again!')
      time.sleep(PERIODICAL_CHECK_INTERVAL) 


def activate_door_switch():
    global GPIO, STATE_DOOR
    print("activate_door_switch: Electronically activating door.")
    if STATE_DOOR == True:
          client.publish("garage/door/state","closing")
    else:
          client.publish("garage/door/state","opening")

    GPIO.output(GARAGE_DRIVE,GPIO.LOW)
    time.sleep(0.5)
    GPIO.output(GARAGE_DRIVE,GPIO.HIGH)
    print("activate_door_switch: Door should be moving now.")


@ask.intent('RPIcontrol', mapping={'status': 'status'})
def gpio_status(status):
    print("status: ", status)
    if status in ['auf','oeffnen', u'\xf6ffnen']:
      state = not GPIO.input(GARAGE_OPEN_SWITCH)
      print('state of switch',state)
      if (state == True):
        return statement('Das Tor ist schon auf.')
      else:
        activate_door_switch()
        return statement(u'Ich oeffne das Tor fuer Dich.'.format(status))

    if status in ['zu','schliessen']:
      state = not GPIO.input(GARAGE_OPEN_SWITCH)
      print('state of switch',state)
      if (state == False):
        return statement('Das Tor ist schon zu.')
      else:
        activate_door_switch()
        return statement('Ich schliesse das Tor fuer Dich.'.format(status))


@ask.intent('RPIstatus')
def gpio_status():
      state = not GPIO.input(GARAGE_OPEN_SWITCH)
      print('state of switch',state)
      if (state == True):
        return statement('Das Tor ist auf.')
      else:
        return statement('Das Tor ist zu.')



def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe("garage/door/switch")
    client.publish("garage/door/open_since","")


def on_message(client, userdata, msg):
    print(msg.topic + " " + str(msg.payload))
    if msg.topic == "garage/door/switch" and msg.payload == "active":
        client.publish("garage/door/switch","idle")
        activate_door_switch()


if __name__ == '__main__':
  port = 5000 #the custom port you want
  # set up periodical check wich will send email if garage
  # stays open for too long
  send_email("Garage Dog startet.")
  EMAIL_SENT = False

  # set up mqtt client
  client = mqtt.Client()
  client.on_connect = on_connect
  client.on_message = on_message
  client.connect(MQTT_SERVER, 1883, 60)

  thread = Thread(target=periodical_check)
  thread.deamon = True
  thread.start()

  thread2 = Thread(target=client.loop_forever)
  thread2.deamon = True
  thread2.start()


  # start flak main function
  app.run(host='localhost', port=port)
