from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "wampar2026"

ADMIN_USUARIO = "admin"
ADMIN_PASSWORD = "wampar123"
ARCHIVO_USUARIOS  = "data/usuarios.txt"
ARCHIVO_MENSAJES  = "data/mensajes.json"
ARCHIVO_CARRITO   = "data/carrito.json"
ARCHIVO_VENTAS    = "data/ventas.json"

os.makedirs("data", exist_ok=True)
for f in [ARCHIVO_MENSAJES, ARCHIVO_CARRITO, ARCHIVO_VENTAS]:
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as fp:
            json.dump([], fp)


# ─── HELPERS ────────────────────────────────────────────────
def leer_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def guardar_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def buscar_usuario(correo):
    try:
        with open(ARCHIVO_USUARIOS, "r", encoding="utf-8") as f:
            for linea in f:
                datos = linea.strip().split(",")
                if datos[0] == correo:
                    return datos
    except FileNotFoundError:
        pass
    return None

def guardar_usuario(nombre, correo, password):
    with open(ARCHIVO_USUARIOS, "a", encoding="utf-8") as f:
        fecha = datetime.now().strftime("%Y-%m")
        f.write(f"{correo},{nombre},{password},{fecha}\n")

def todos_usuarios():
    usuarios = []
    try:
        with open(ARCHIVO_USUARIOS, "r", encoding="utf-8") as f:
            for linea in f:
                datos = linea.strip().split(",")
                if len(datos) >= 3:
                    usuarios.append({
                        "correo": datos[0],
                        "nombre": datos[1],
                        "fecha":  datos[3] if len(datos) >= 4 else datetime.now().strftime("%Y-%m")
                    })
    except FileNotFoundError:
        pass
    return usuarios

def mensajes_no_leidos(correo):
    mensajes = leer_json(ARCHIVO_MENSAJES)
    return sum(1 for m in mensajes if m.get("para") == correo and not m.get("leido", False))


# ─── RUTAS PÚBLICAS ─────────────────────────────────────────
@app.route("/")
def index():
    nombre   = session.get("nombre", None)
    correo   = session.get("usuario", None)
    notif    = mensajes_no_leidos(correo) if correo and correo != ADMIN_USUARIO else 0
    carrito  = leer_json(ARCHIVO_CARRITO)
    mi_carrito = [c for c in carrito if c.get("correo") == correo]
    total_items = sum(c.get("cantidad", 0) for c in mi_carrito)
    return render_template("index.html", nombre=nombre, notif=notif, total_items=total_items)

@app.route("/login", methods=["GET", "POST"])
def login():
    if "usuario" in session:
        return redirect(url_for("admin") if session["usuario"] == ADMIN_USUARIO else url_for("index"))
    mensaje = ""
    if request.method == "POST":
        correo   = request.form["correo"]
        password = request.form["password"]
        if correo == ADMIN_USUARIO and password == ADMIN_PASSWORD:
            session["usuario"] = ADMIN_USUARIO
            session["nombre"]  = "Admin"
            return redirect(url_for("admin"))
        datos = buscar_usuario(correo)
        if datos and datos[2] == password:
            session["usuario"] = correo
            session["nombre"]  = datos[1]
            return redirect(url_for("index"))
        else:
            mensaje = "Correo o contraseña incorrectos."
    return render_template("login.html", mensaje=mensaje)

@app.route("/registro", methods=["GET", "POST"])
def registro():
    mensaje = ""
    tipo = ""
    if request.method == "POST":
        nombre   = request.form["nombre"]
        correo   = request.form["correo"]
        password = request.form["password"]
        if buscar_usuario(correo):
            mensaje = "Este correo ya está registrado."
            tipo = "error"
        else:
            guardar_usuario(nombre, correo, password)
            mensaje = "Cuenta creada. Ya puedes iniciar sesión."
            tipo = "ok"
    return render_template("registro.html", mensaje=mensaje, tipo=tipo)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/contactanos")
def contactanos():
    if "usuario" not in session or session["usuario"] == ADMIN_USUARIO:
        return redirect(url_for("login"))
    correo  = session["usuario"]
    nombre  = session["nombre"]
    mensajes = leer_json(ARCHIVO_MENSAJES)
    # Marcar como leídos los mensajes para este usuario
    for m in mensajes:
        if m.get("para") == correo:
            m["leido"] = True
    guardar_json(ARCHIVO_MENSAJES, mensajes)
    # Filtrar hilo del usuario
    hilo = [m for m in mensajes if m.get("de") == correo or m.get("para") == correo]
    return render_template("contactanos.html", nombre=nombre, correo=correo, hilo=hilo)


# ─── API MENSAJES ────────────────────────────────────────────
@app.route("/api/mensaje", methods=["POST"])
def api_mensaje():
    if "usuario" not in session:
        return jsonify({"success": False})
    data    = request.get_json()
    texto   = data.get("texto", "").strip()
    if not texto:
        return jsonify({"success": False})
    correo  = session["usuario"]
    nombre  = session["nombre"]
    mensajes = leer_json(ARCHIVO_MENSAJES)
    mensajes.append({
        "id":     len(mensajes) + 1,
        "de":     correo,
        "nombre": nombre,
        "para":   ADMIN_USUARIO,
        "texto":  texto,
        "fecha":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "leido":  False
    })
    guardar_json(ARCHIVO_MENSAJES, mensajes)
    return jsonify({"success": True})

@app.route("/api/admin/mensaje", methods=["POST"])
def api_admin_mensaje():
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False})
    data   = request.get_json()
    para   = data.get("para", "")
    texto  = data.get("texto", "").strip()
    if not texto or not para:
        return jsonify({"success": False})
    mensajes = leer_json(ARCHIVO_MENSAJES)
    mensajes.append({
        "id":     len(mensajes) + 1,
        "de":     ADMIN_USUARIO,
        "nombre": "Wampar Sport",
        "para":   para,
        "texto":  texto,
        "fecha":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "leido":  False
    })
    guardar_json(ARCHIVO_MENSAJES, mensajes)
    return jsonify({"success": True})

@app.route("/api/mensajes/nuevos")
def api_mensajes_nuevos():
    if "usuario" not in session:
        return jsonify({"count": 0})
    correo = session["usuario"]
    return jsonify({"count": mensajes_no_leidos(correo)})

@app.route("/api/mensajes/hilo")
def api_mensajes_hilo():
    if "usuario" not in session:
        return jsonify([])
    correo   = session["usuario"]
    mensajes = leer_json(ARCHIVO_MENSAJES)
    hilo     = [m for m in mensajes if m.get("de") == correo or m.get("para") == correo]
    return jsonify(hilo)


# ─── API CARRITO ─────────────────────────────────────────────
@app.route("/api/carrito/agregar", methods=["POST"])
def api_carrito_agregar():
    if "usuario" not in session or session["usuario"] == ADMIN_USUARIO:
        return jsonify({"success": False, "mensaje": "Debes iniciar sesión."})
    data     = request.get_json()
    producto = data.get("producto", "")
    precio   = data.get("precio", 0)
    correo   = session["usuario"]
    nombre   = session["nombre"]
    carrito  = leer_json(ARCHIVO_CARRITO)
    # Buscar si ya existe
    for item in carrito:
        if item["correo"] == correo and item["producto"] == producto:
            item["cantidad"] += 1
            guardar_json(ARCHIVO_CARRITO, carrito)
            return jsonify({"success": True, "total": sum(c["cantidad"] for c in carrito if c["correo"] == correo)})
    carrito.append({
        "correo":   correo,
        "nombre":   nombre,
        "producto": producto,
        "precio":   precio,
        "cantidad": 1,
        "fecha":    datetime.now().strftime("%Y-%m")
    })
    guardar_json(ARCHIVO_CARRITO, carrito)
    # Registrar venta
    ventas = leer_json(ARCHIVO_VENTAS)
    ventas.append({
        "correo":   correo,
        "producto": producto,
        "precio":   precio,
        "fecha":    datetime.now().strftime("%Y-%m")
    })
    guardar_json(ARCHIVO_VENTAS, ventas)
    total = sum(c["cantidad"] for c in carrito if c["correo"] == correo)
    return jsonify({"success": True, "total": total})

@app.route("/api/carrito/obtener")
def api_carrito_obtener():
    if "usuario" not in session:
        return jsonify([])
    correo  = session["usuario"]
    carrito = leer_json(ARCHIVO_CARRITO)
    return jsonify([c for c in carrito if c["correo"] == correo])

@app.route("/api/carrito/eliminar", methods=["POST"])
def api_carrito_eliminar():
    if "usuario" not in session:
        return jsonify({"success": False})
    data     = request.get_json()
    producto = data.get("producto", "")
    correo   = session["usuario"]
    carrito  = leer_json(ARCHIVO_CARRITO)
    carrito  = [c for c in carrito if not (c["correo"] == correo and c["producto"] == producto)]
    guardar_json(ARCHIVO_CARRITO, carrito)
    return jsonify({"success": True})


# ─── PANEL ADMIN ────────────────────────────────────────────
@app.route("/admin")
def admin():
    if session.get("usuario") != ADMIN_USUARIO:
        return redirect(url_for("login"))
    usuarios = todos_usuarios()
    mensajes = leer_json(ARCHIVO_MENSAJES)
    carrito  = leer_json(ARCHIVO_CARRITO)
    ventas   = leer_json(ARCHIVO_VENTAS)
    notif_admin = sum(1 for m in mensajes if m.get("para") == ADMIN_USUARIO and not m.get("leido", False))
    return render_template("admin.html",
        usuarios=usuarios,
        mensajes=mensajes,
        carrito=carrito,
        ventas=ventas,
        notif_admin=notif_admin
    )

@app.route("/api/admin/usuario", methods=["POST"])
def admin_usuario():
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False, "mensaje": "No autorizado."})
    data           = request.get_json()
    accion         = data.get("accion")
    correo         = data.get("correo", "").strip()
    nuevo_nombre   = data.get("nombre", "").strip()
    nuevo_password = data.get("password", "").strip()

    if accion == "buscar":
        datos = buscar_usuario(correo)
        if datos:
            return jsonify({"success": True, "mensaje": "Usuario encontrado.", "usuario": {"nombre": datos[1], "correo": datos[0]}})
        return jsonify({"success": False, "mensaje": "Correo no encontrado."})

    elif accion == "modificar":
        lineas = []
        encontrado = False
        try:
            with open(ARCHIVO_USUARIOS, "r", encoding="utf-8") as f:
                for linea in f:
                    datos = linea.strip().split(",")
                    if datos[0] == correo:
                        nombre_final = nuevo_nombre if nuevo_nombre else datos[1]
                        pass_final   = nuevo_password if nuevo_password else datos[2]
                        fecha        = datos[3] if len(datos) >= 4 else datetime.now().strftime("%Y-%m")
                        lineas.append(f"{correo},{nombre_final},{pass_final},{fecha}\n")
                        encontrado = True
                    else:
                        lineas.append(linea)
            with open(ARCHIVO_USUARIOS, "w", encoding="utf-8") as f:
                f.writelines(lineas)
            return jsonify({"success": encontrado, "mensaje": "Usuario modificado." if encontrado else "No encontrado."})
        except FileNotFoundError:
            return jsonify({"success": False, "mensaje": "No hay usuarios."})

    elif accion == "eliminar":
        lineas = []
        encontrado = False
        try:
            with open(ARCHIVO_USUARIOS, "r", encoding="utf-8") as f:
                for linea in f:
                    datos = linea.strip().split(",")
                    if datos[0] == correo:
                        encontrado = True
                    else:
                        lineas.append(linea)
            with open(ARCHIVO_USUARIOS, "w", encoding="utf-8") as f:
                f.writelines(lineas)
            return jsonify({"success": encontrado, "mensaje": "Usuario eliminado." if encontrado else "No encontrado."})
        except FileNotFoundError:
            return jsonify({"success": False, "mensaje": "No hay usuarios."})

    return jsonify({"success": False, "mensaje": "Acción no válida."})

@app.route("/api/admin/mensajes/hilo")
def api_admin_mensajes_hilo():
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify([])
    correo   = request.args.get("correo", "")
    mensajes = leer_json(ARCHIVO_MENSAJES)
    # Marcar leídos los mensajes del usuario hacia admin
    for m in mensajes:
        if m.get("de") == correo and m.get("para") == ADMIN_USUARIO:
            m["leido"] = True
    guardar_json(ARCHIVO_MENSAJES, mensajes)
    hilo = [m for m in mensajes if m.get("de") == correo or m.get("para") == correo]
    return jsonify(hilo)

@app.route("/api/admin/notif")
def api_admin_notif():
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"count": 0})
    mensajes = leer_json(ARCHIVO_MENSAJES)
    count = sum(1 for m in mensajes if m.get("para") == ADMIN_USUARIO and not m.get("leido", False))
    return jsonify({"count": count})

if __name__ == "__main__":
    app.run(debug=True)
