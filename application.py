import os
import requests
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room, leave_room


app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
socketio = SocketIO(app)


displaynames = []
channels = []
recents = {}
messages = {}
users = {}

@app.route("/")
def index():
	if 'username' not in session:
		return render_template('login.html')
	
	name = session['username']
	if name in recents:
		return redirect(url_for('chat'))
	return render_template('index.html',name=name, channels=channels)

@app.route('/login',methods=['GET','POST'])
def login():
	if request.method == "POST":
		displayname=request.form.get('name')
		if displayname:
			if displayname in displaynames:
				return render_template('login.html',message="Displayname Already Taken")
			session['username']=displayname
			displaynames.append(displayname)
			return redirect(url_for('index'))
	return render_template('login.html')

@app.route('/logout')
def logout():
	if 'username' not in session:
		return render_template('login.html')
	
	name = session['username']
	recents.pop(name,None)
	if name in displaynames:
		displaynames.remove(name)
	session.pop('username',None)
	return render_template('login.html')

@app.route('/addch',methods=['POST'])
def addch():
	if request.method == "POST":
		if 'username' not in session:
			return render_template('login.html')

		channel = request.form.get('channel')
		if channel in channels:
			return render_template('index.html',name=session['username'], channels=channels, message="Channel Name Already Exists")
		channels.append(channel)
	return redirect(url_for('index'))

@app.route('/recent/<string:ch>')
def recent(ch):
	if 'username' not in session:
		return render_template('login.html')
	name = session['username']
	recents[name] = ch
	return redirect(url_for('chat'))

@app.route('/chat')
def chat():
	if "username" not in session:
		return render_template('login.html')
	name = session['username']
	channel0 = recents[name]
	return render_template('chat.html',displayname=name,channel=channel0)


@app.route('/remove_recent/<string:ch>')
def remove_recent(ch):
	if "username" not in session:
		return render_template('login.html')

	recents.pop(session['username'],None)
	return redirect(url_for('index'))

@socketio.on('join_channel')
def handle_join_channel_event(data):
	channel = data['channel']
	name = data['displayname']
	print(channel, name)
	join_room(channel)
	if channel in messages:
		old_chats = messages[channel]
		for chat in old_chats:
			data = {'name':name,'chat':chat}
			socketio.emit('retrive_old_messages',data,room=channel)

@socketio.on('send_message')
def handle_channel_message(data):
	channel = data['channel']
	timeObj = datetime.now()
	timeStr = timeObj.strftime("%H:%M")
	data['timestamp'] = timeStr
	print(data['message'])
	if channel not in messages:
		messages[channel] = []
	if len(messages[channel]) >= 100:
		del messages[channel][0]
	messages[channel].append({'displayname':data['displayname'],'message':data['message'],'timestamp':data['timestamp']})
	socketio.emit('receive_message', data, room=channel)

@socketio.on('username')
def get_username(username):
    users[username] = request.sid

@socketio.on('send_private_message')
def handle_private_message(data):
	if data['recipient'] not in users:
		socketio.emit('user_not_found',data['recipient'],room=request.sid)
	else:
		recipient_session_id = users[data['recipient']]
		timeObj = datetime.now()
		timeStr = timeObj.strftime("%H:%M")
		data['timestamp'] = timeStr
		socketio.emit('receive_private_message',data,room=request.sid)
		socketio.emit('receive_private_message',data,room=recipient_session_id)

if __name__ == '__main__':
    socketio.run(app, debug=True)