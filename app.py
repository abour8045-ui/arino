import os
from flask import Flask, render_template_string, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "arino_prod_secret"

# 🔥 مهم: دیتابیس برای Render
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///arino.db"
).replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ================= DATABASE =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(200))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50))
    room = db.Column(db.String(100))
    text = db.Column(db.Text)

class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50))
    room = db.Column(db.String(100))
    text = db.Column(db.Text)

with app.app_context():
    db.create_all()

# ================= HELPERS =================
def dm_room(u1, u2):
    return "_".join(sorted([u1, u2]))

# ================= FRONTEND =================
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Arino PRO</title>
<style>
body{background:#0f0f0f;color:white;font-family:tahoma}
.box{width:420px;margin:auto;background:#1c1c1c;padding:15px;border-radius:10px;margin-top:20px}
input,button{width:90%;padding:10px;margin:5px}
#chat,#dm{height:200px;overflow:auto;background:#000;padding:10px}
.msg{background:#333;margin:5px;padding:5px;border-radius:5px}
.user{color:#4af}
</style>
</head>
<body>

<div class="box">
<h2>📱 Arino PRO (Production)</h2>

<input id="u" placeholder="username">
<input id="p" placeholder="password">
<button onclick="register()">ثبت نام</button>
<button onclick="login()">ورود</button>

<hr>

<h3>💬 گروه</h3>
<input id="room" placeholder="group name">
<button onclick="joinGroup()">ورود</button>

<div id="chat"></div>
<input id="msg" placeholder="پیام گروه">
<button onclick="sendGroup()">ارسال</button>

<hr>

<h3>💌 پیام خصوصی</h3>
<input id="to" placeholder="username">
<button onclick="joinDM()">باز کردن DM</button>

<div id="dm"></div>
<input id="dmmsg" placeholder="پیام خصوصی">
<button onclick="sendDM()">ارسال</button>

</div>

<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
let socket = io();
let group = "";
let dmRoom = "";

function register(){
fetch("/register",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({u:u.value,p:p.value})})
.then(r=>r.json()).then(d=>alert(d.msg));
}

function login(){
fetch("/login",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({u:u.value,p:p.value})})
.then(r=>r.json()).then(d=>alert(d.msg));
}

// ===== GROUP =====
function joinGroup(){
group = room.value;
socket.emit("join_group",group);
chat.innerHTML="";
}

function sendGroup(){
socket.emit("group_msg",{room:group,text:msg.value});
msg.value="";
}

socket.on("group_msg",d=>{
chat.innerHTML += `<div class='msg'><b>${d.user}</b>: ${d.text}</div>`;
});

// ===== DM =====
function joinDM(){
let to = document.getElementById("to").value;
dmRoom = to;
socket.emit("join_dm",{user:to});
dm.innerHTML="";
}

function sendDM(){
socket.emit("dm_msg",{to:dmRoom,text:dmmsg.value});
dmmsg.value="";
}

socket.on("dm_msg",d=>{
dm.innerHTML += `<div class='msg'><b>${d.user}</b>: ${d.text}</div>`;
});
</script>

</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

# ================= AUTH =================
@app.route("/register", methods=["POST"])
def register():
    d=request.json
    if User.query.filter_by(username=d["u"]).first():
        return jsonify({"msg":"وجود دارد ❌"})

    u=User(username=d["u"],password=generate_password_hash(d["p"]))
    db.session.add(u)
    db.session.commit()
    return jsonify({"msg":"ثبت شد ✅"})

@app.route("/login", methods=["POST"])
def login():
    d=request.json
    u=User.query.filter_by(username=d["u"]).first()

    if u and check_password_hash(u.password,d["p"]):
        session["user"]=u.username
        return jsonify({"msg":"ورود موفق ✅"})
    return jsonify({"msg":"اشتباه ❌"})

# ================= SOCKET =================
@socketio.on("join_group")
def join_group(room):
    join_room(room)

@socketio.on("group_msg")
def group_msg(data):
    user=session.get("user","guest")
    emit("group_msg",{"user":user,"text":data["text"]},to=data["room"])

# ----- DM -----
@socketio.on("join_dm")
def join_dm(data):
    u1=session.get("user","guest")
    u2=data["user"]
    room=dm_room(u1,u2)
    join_room(room)

@socketio.on("dm_msg")
def dm_msg(data):
    user=session.get("user","guest")
    room=dm_room(user,data["to"])

    emit("dm_msg",{
        "user":user,
        "text":data["text"]
    },to=room)

# ================= RUN =================
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))