#!/usr/bin/env python
# coding: utf-8

# Copyright 2017 Taylor Arnett
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, redirect, url_for, Response
from flask_sockets import Sockets
import gevent
from gevent import queue
import json

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

CLIENTS = list()


class Client:
    """
    Client class based off of Abram Hindle's chat.py repo Apache License, Version 2.0 https://github.com/abramhindle/WebSocketsExamples/blob/master/chat.py
    """
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()  # return an item after removing it


class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()

    def add_set_listener(self, listener):
        self.listeners.append(listener)

    def update(self, entity, key, value):
        entry = self.space.get(entity, dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners(entity)

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners(entity)

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity, dict())

    def world(self):
        return self.space


myWorld = World()


def set_listener(entity, data):
    ''' do something with the update ! '''
    send_json({entity:data})


def send_json(data):
    """
    sends json to all the clients
    """
    j = json.dumps(data)
    for client in CLIENTS:
        client.put(j)


myWorld.add_set_listener(set_listener)


@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return redirect(url_for("static", filename="index.html"))


def read_ws(ws, client):
    '''A greenlet function that reads from the websocket and updates the world'''
    # From Abram Hindles Web Socket Examples Apache License, Version 2.0 https://github.com/abramhindle/WebSocketsExamples/blob/master/chat.py on March 15, 2017
    try:
        while True:
            message = ws.receive()
            # print "WS RECV: %s" % message
            if message is not None:
                packet = json.loads(message)

                for k,v in packet.items():
                    myWorld.set(k, v)
            else:
                break
    except:
        pass


@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    client = Client()
    CLIENTS.append(client)  # add it to the global clients list
    g = gevent.spawn(read_ws, ws, client)

    ws.send(json.dumps(myWorld.world()))  # give each client access to the world when they subscribe

    try:
        while True: # continuously read from the client
            message = client.get()
            ws.send(message)
    except Exception as e:
        print "WS Error %s" % e

    finally:
        CLIENTS.remove(client)
        gevent.kill(g)


def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data != ''):
        return json.loads(request.data)
    else:
        return json.loads(request.form.keys()[0])


@app.route("/entity/<entity>", methods=['POST', 'PUT'])
def update(entity):
    '''update the entities via this interface'''
    # Code reused from AJAX assignment 4
    # get raw data from post/put
    json_payload = flask_post_json()

    if request.method == 'POST':
        for k in json_payload:
            myWorld.update(entity, k, json_payload[k])

    else:
        myWorld.set(entity, json_payload)

    # entity in world
    entity_world_instance = myWorld.get(entity)
    return flask.jsonify(entity_world_instance), 200


@app.route("/world", methods=['POST', 'GET'])
def world():
    '''you should probably return the world here'''
    return flask.jsonify(myWorld.world()), 200


@app.route("/entity/<entity>")
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    return flask.jsonify(myWorld.get(entity)), 200


@app.route("/clear", methods=['POST', 'GET'])
def clear():
    '''Clear the world out!'''
    # must return a response
    myWorld.clear()
    return Response("world cleared!", 200)


if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
