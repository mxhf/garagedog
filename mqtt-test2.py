#!/usr/bin/env python
import paho.mqtt.client as mqtt
import time

def on_connect(client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        client.subscribe("garage/door/switch")
        client.subscribe("garage/door/status")

def on_message(client, userdata, msg):
        print("Foo")
        print(msg.topic + " " + str(msg.payload))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("192.168.2.139", 1883, 60)

client.loop_forever()
