from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "wampar2026"

ADMIN_USUARIO = "admin"
ADMIN_PASSWORD = "wampar123"
ARCHIVO_USUARIOS = "data/usuarios.txt"
ARCHIVO_MENSAJES = "data/mensajes.json"
ARCHIVO_CARRITO  = "data/carrito.json"

# Precios base de cada producto (productos con talla)
PRECIOS_PRODUCTOS = {
    "Camiseta": 30,
    "Camiseta + Short + Medias": 55,
    "Bividi": 20,
    "Short": 20,
}
TALLAS_VALIDAS = ["2", "4", "6", "8", "10", "12", "14", "16", "S", "M", "L", "XL", "XXL", "XXXL"]

# Banderola se vende por metro (la tela mide 1.50m de alto siempre, el cliente elige el ancho en metros)
PRECIO_METRO_BANDEROLA = 40
MAX_METROS_BANDEROLA = 100
MAX_CANTIDAD_POR_TALLA = 500  # límite razonable por línea de pedido (evita valores absurdos por error de tipeo)
MAX_MONTO_ADELANTO = 5000  # límite razonable en soles (evita errores de tipeo como agregar un cero de más)

os.makedirs("data", exist_ok=True)
for f in [ARCHIVO_MENSAJES, ARCHIVO_CARRITO]:
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

def siguiente_id_carrito():
    carrito = leer_json(ARCHIVO_CARRITO)
    if not carrito:
        return 1
    return max(c.get("id", 0) for c in carrito) + 1

def siguiente_id_desde_lista(carrito):
    """Igual que siguiente_id_carrito pero calculando sobre una lista ya cargada en memoria
    (necesario cuando se agregan varios items en el mismo request, antes de guardar a disco)."""
    if not carrito:
        return 1
    return max(c.get("id", 0) for c in carrito) + 1


# ─── RUTAS PÚBLICAS ─────────────────────────────────────────
@app.route("/")
def index():
    nombre  = session.get("nombre", None)
    correo  = session.get("usuario", None)
    notif   = mensajes_no_leidos(correo) if correo and correo != ADMIN_USUARIO else 0
    carrito = leer_json(ARCHIVO_CARRITO)
    mi_carrito  = [c for c in carrito if c.get("correo") == correo and c.get("estado") == "en_carrito"]
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

@app.route("/mis-compras")
def mis_compras():
    if "usuario" not in session or session["usuario"] == ADMIN_USUARIO:
        return redirect(url_for("login"))
    correo  = session["usuario"]
    nombre  = session["nombre"]
    notif   = mensajes_no_leidos(correo)
    carrito = leer_json(ARCHIVO_CARRITO)
    compras = [c for c in carrito if c.get("correo") == correo
               and c.get("estado") in ("esperando_aprobacion", "aceptado", "rechazado")]
    compras.sort(key=lambda c: c.get("fecha", ""), reverse=True)
    pedidos = agrupar_compras(compras)
    return render_template("mis_compras.html", nombre=nombre, notif=notif, pedidos=pedidos)

@app.route("/contactanos")
def contactanos():
    if "usuario" not in session or session["usuario"] == ADMIN_USUARIO:
        return render_template("contactanos.html", sin_sesion=True)
    correo   = session["usuario"]
    nombre   = session["nombre"]
    mensajes = leer_json(ARCHIVO_MENSAJES)
    for m in mensajes:
        if m.get("para") == correo:
            m["leido"] = True
    guardar_json(ARCHIVO_MENSAJES, mensajes)
    hilo = [m for m in mensajes if m.get("de") == correo or m.get("para") == correo]
    return render_template("contactanos.html", nombre=nombre, correo=correo, hilo=hilo, sin_sesion=False)


# ─── API MENSAJES ────────────────────────────────────────────
CARPETA_IMG_CHAT = "static/img/chat"
os.makedirs(CARPETA_IMG_CHAT, exist_ok=True)

def guardar_imagen_chat(imagen_base64):
    """Guarda una imagen enviada en base64 (data URL) como archivo y devuelve la ruta relativa para mostrarla."""
    import base64, uuid
    try:
        encabezado, datos = imagen_base64.split(",", 1)
        ext = "png"
        if "jpeg" in encabezado or "jpg" in encabezado:
            ext = "jpg"
        elif "gif" in encabezado:
            ext = "gif"
        elif "webp" in encabezado:
            ext = "webp"
        nombre_archivo = f"{uuid.uuid4().hex}.{ext}"
        ruta = os.path.join(CARPETA_IMG_CHAT, nombre_archivo)
        with open(ruta, "wb") as f:
            f.write(base64.b64decode(datos))
        return f"img/chat/{nombre_archivo}"
    except Exception:
        return None

@app.route("/api/mensaje", methods=["POST"])
def api_mensaje():
    if "usuario" not in session:
        return jsonify({"success": False})
    data    = request.get_json()
    texto   = data.get("texto", "").strip()
    imagen  = data.get("imagen")  # data URL base64, opcional
    ruta_img = guardar_imagen_chat(imagen) if imagen else None
    if not texto and not ruta_img:
        return jsonify({"success": False})
    correo   = session["usuario"]
    nombre   = session["nombre"]
    mensajes = leer_json(ARCHIVO_MENSAJES)
    mensajes.append({
        "id": len(mensajes) + 1, "de": correo, "nombre": nombre, "para": ADMIN_USUARIO,
        "texto": texto, "imagen": ruta_img, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "leido": False
    })
    guardar_json(ARCHIVO_MENSAJES, mensajes)
    return jsonify({"success": True})

@app.route("/api/admin/mensaje", methods=["POST"])
def api_admin_mensaje():
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False})
    data    = request.get_json()
    para    = data.get("para", "")
    texto   = data.get("texto", "").strip()
    imagen  = data.get("imagen")
    ruta_img = guardar_imagen_chat(imagen) if imagen else None
    if (not texto and not ruta_img) or not para:
        return jsonify({"success": False})
    mensajes = leer_json(ARCHIVO_MENSAJES)
    mensajes.append({
        "id": len(mensajes) + 1, "de": ADMIN_USUARIO, "nombre": "Wampar Sport", "para": para,
        "texto": texto, "imagen": ruta_img, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "leido": False
    })
    guardar_json(ARCHIVO_MENSAJES, mensajes)
    return jsonify({"success": True})

@app.route("/api/mensajes/nuevos")
def api_mensajes_nuevos():
    if "usuario" not in session:
        return jsonify({"count": 0})
    return jsonify({"count": mensajes_no_leidos(session["usuario"])})

@app.route("/api/mensajes/hilo")
def api_mensajes_hilo():
    if "usuario" not in session:
        return jsonify([])
    correo   = session["usuario"]
    mensajes = leer_json(ARCHIVO_MENSAJES)
    hilo     = [m for m in mensajes if m.get("de") == correo or m.get("para") == correo]
    return jsonify(hilo)


# ─── API CARRITO (lado usuario) ──────────────────────────────
@app.route("/api/carrito/agregar", methods=["POST"])
def api_carrito_agregar():
    if "usuario" not in session or session["usuario"] == ADMIN_USUARIO:
        return jsonify({"success": False, "mensaje": "Debes iniciar sesión."})
    data     = request.get_json()
    producto = data.get("producto", "")
    correo   = session["usuario"]
    nombre   = session["nombre"]
    carrito  = leer_json(ARCHIVO_CARRITO)
    grupo_id = data.get("grupo_id") or datetime.now().strftime("%Y%m%d%H%M%S%f")

    if producto == "Banderola":
        metros = data.get("metros", 0)
        try:
            metros = float(metros)
        except (TypeError, ValueError):
            return jsonify({"success": False, "mensaje": "Cantidad de metros no válida."})
        if metros <= 0 or metros > MAX_METROS_BANDEROLA:
            return jsonify({"success": False, "mensaje": f"La cantidad de metros debe estar entre 0 y {MAX_METROS_BANDEROLA}."})
        precio_unit = PRECIO_METRO_BANDEROLA
        detalle = f'{metros:.2f} metros (1.50m alto x {metros:.2f}m ancho)'
        carrito.append({
            "id": siguiente_id_carrito(), "correo": correo, "nombre": nombre,
            "producto": producto, "precio": precio_unit, "cantidad": metros,
            "detalle": detalle, "grupo_id": grupo_id,
            "estado": "en_carrito", "entrega": "pendiente",
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        guardar_json(ARCHIVO_CARRITO, carrito)
        total = sum(c["cantidad"] for c in carrito if c["correo"] == correo and c.get("estado") == "en_carrito")
        return jsonify({"success": True, "total": round(total, 2)})

    # Productos con tallas: se espera data.tallas = {"S": 2, "M": 1, ...}
    tallas = data.get("tallas", {})
    if not isinstance(tallas, dict) or not tallas:
        return jsonify({"success": False, "mensaje": "Selecciona al menos una talla y cantidad."})

    precio_unit = PRECIOS_PRODUCTOS.get(producto)
    if precio_unit is None:
        return jsonify({"success": False, "mensaje": "Producto no válido."})

    agregados = 0
    errores_talla = []
    for talla, cant in tallas.items():
        if talla not in TALLAS_VALIDAS:
            continue
        try:
            cant = int(cant)
        except (TypeError, ValueError):
            errores_talla.append(f"Talla {talla}: la cantidad debe ser un número entero.")
            continue
        if cant <= 0:
            errores_talla.append(f"Talla {talla}: la cantidad debe ser mayor a 0.")
            continue
        if cant > MAX_CANTIDAD_POR_TALLA:
            errores_talla.append(f"Talla {talla}: la cantidad máxima permitida por pedido es {MAX_CANTIDAD_POR_TALLA}.")
            continue
        agregados += cant
        # Si ya existe la misma talla del mismo producto en el carrito (sin confirmar), suma cantidad
        existente = next((c for c in carrito if c["correo"] == correo and c["producto"] == producto
                           and c.get("talla") == talla and c.get("estado") == "en_carrito"), None)
        if existente:
            existente["cantidad"] += cant
        else:
            carrito.append({
                "id": siguiente_id_desde_lista(carrito), "correo": correo, "nombre": nombre,
                "producto": producto, "precio": precio_unit, "cantidad": cant,
                "talla": talla, "detalle": f"Talla {talla}", "grupo_id": grupo_id,
                "estado": "en_carrito", "entrega": "pendiente",
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
            })

    if agregados == 0:
        mensaje = " ".join(errores_talla) if errores_talla else "Selecciona al menos una talla y cantidad."
        return jsonify({"success": False, "mensaje": mensaje})

    guardar_json(ARCHIVO_CARRITO, carrito)
    total = sum(c["cantidad"] for c in carrito if c["correo"] == correo and c.get("estado") == "en_carrito")
    return jsonify({"success": True, "total": round(total, 2)})

@app.route("/api/carrito/obtener")
def api_carrito_obtener():
    if "usuario" not in session:
        return jsonify([])
    correo  = session["usuario"]
    carrito = leer_json(ARCHIVO_CARRITO)
    return jsonify([c for c in carrito if c["correo"] == correo and c.get("estado") == "en_carrito"])

@app.route("/api/carrito/cantidad", methods=["POST"])
def api_carrito_cantidad():
    if "usuario" not in session:
        return jsonify({"success": False})
    data    = request.get_json()
    id_item = data.get("id")
    accion  = data.get("accion")
    correo  = session["usuario"]
    carrito = leer_json(ARCHIVO_CARRITO)
    for item in carrito:
        if item["id"] == id_item and item["correo"] == correo:
            if accion == "sumar":
                item["cantidad"] += 1
            elif accion == "restar":
                item["cantidad"] -= 1
                if item["cantidad"] <= 0:
                    carrito.remove(item)
            break
    guardar_json(ARCHIVO_CARRITO, carrito)
    return jsonify({"success": True})

@app.route("/api/carrito/eliminar", methods=["POST"])
def api_carrito_eliminar():
    if "usuario" not in session:
        return jsonify({"success": False})
    data    = request.get_json()
    id_item = data.get("id")
    correo  = session["usuario"]
    carrito = leer_json(ARCHIVO_CARRITO)
    carrito = [c for c in carrito if not (c["id"] == id_item and c["correo"] == correo)]
    guardar_json(ARCHIVO_CARRITO, carrito)
    return jsonify({"success": True})

@app.route("/api/carrito/confirmar", methods=["POST"])
def api_carrito_confirmar():
    if "usuario" not in session or session["usuario"] == ADMIN_USUARIO:
        return jsonify({"success": False, "mensaje": "Debes iniciar sesión."})
    correo  = session["usuario"]
    carrito = leer_json(ARCHIVO_CARRITO)
    encontrados = False
    fecha_confirmacion = datetime.now().strftime("%Y-%m-%d %H:%M")
    pedido_id = datetime.now().strftime("%Y%m%d%H%M%S")
    for item in carrito:
        if item["correo"] == correo and item.get("estado") == "en_carrito":
            item["estado"]    = "esperando_aprobacion"
            item["entrega"]   = "pendiente"
            item["adelanto"]  = 0
            item["fecha"]     = fecha_confirmacion
            item["pedido_id"] = pedido_id  # mismo id para todo lo confirmado en este checkout -> permite agrupar en el admin
            encontrados = True
    if not encontrados:
        return jsonify({"success": False, "mensaje": "Tu carrito está vacío."})
    guardar_json(ARCHIVO_CARRITO, carrito)
    return jsonify({"success": True, "mensaje": "¡Pedido enviado! Puedes modificarlo mientras la tienda no lo haya aceptado."})


@app.route("/api/pedido/cancelar", methods=["POST"])
def api_pedido_cancelar():
    """El cliente cancela TODO su pedido mientras sigue en estado 'esperando_aprobacion' (aún no fue aceptado)."""
    if "usuario" not in session:
        return jsonify({"success": False})
    correo = session["usuario"]
    data = request.get_json() or {}
    pedido_id = data.get("pedido_id")
    carrito = leer_json(ARCHIVO_CARRITO)
    encontrado = False
    nuevo_carrito = []
    for item in carrito:
        if item.get("correo") == correo and item.get("pedido_id") == pedido_id and item.get("estado") == "esperando_aprobacion":
            encontrado = True
            continue  # se elimina
        nuevo_carrito.append(item)
    if not encontrado:
        return jsonify({"success": False, "mensaje": "Ese pedido ya no se puede cancelar (puede que la tienda ya lo haya aceptado)."})
    guardar_json(ARCHIVO_CARRITO, nuevo_carrito)
    return jsonify({"success": True})


@app.route("/api/pedido/modificar_cantidad", methods=["POST"])
def api_pedido_modificar_cantidad():
    """El cliente ajusta la cantidad de una línea de su pedido mientras sigue 'esperando_aprobacion'."""
    if "usuario" not in session:
        return jsonify({"success": False})
    correo = session["usuario"]
    data = request.get_json() or {}
    item_id = data.get("id")
    accion = data.get("accion")
    carrito = leer_json(ARCHIVO_CARRITO)
    nuevo_carrito = []
    actualizado = False
    for item in carrito:
        if item.get("id") == item_id and item.get("correo") == correo and item.get("estado") == "esperando_aprobacion":
            if accion == "sumar":
                item["cantidad"] += 1
            elif accion == "restar":
                item["cantidad"] -= 1
                if item["cantidad"] <= 0:
                    actualizado = True
                    continue  # se elimina esta línea
            actualizado = True
        nuevo_carrito.append(item)
    if not actualizado:
        return jsonify({"success": False, "mensaje": "Ese pedido ya no se puede modificar."})
    guardar_json(ARCHIVO_CARRITO, nuevo_carrito)
    return jsonify({"success": True})


# ─── PANEL ADMIN ────────────────────────────────────────────
def agrupar_compras(compras):
    """Agrupa los productos de una misma compra (mismo pedido_id, o si no existe, mismo correo+fecha)
    para que el admin los vea como un solo pedido con varios productos, no como filas sueltas."""
    grupos = {}
    orden = []
    for c in compras:
        clave = c.get("pedido_id") or f"{c.get('correo')}|{c.get('fecha')}"
        if clave not in grupos:
            grupos[clave] = {
                "clave": clave,
                "correo": c.get("correo"),
                "nombre": c.get("nombre"),
                "fecha": c.get("fecha"),
                "estado": c.get("estado"),  # esperando_aprobacion / aceptado / rechazado
                "adelanto": c.get("adelanto", 0),
                "productos": [],
                "total": 0,
                "todos_entregados": True,
                "algun_pendiente": False,
            }
            orden.append(clave)
        g = grupos[clave]
        g["productos"].append(c)
        g["total"] += c.get("precio", 0) * c.get("cantidad", 0)
        if c.get("entrega") == "entregado":
            g["algun_pendiente"] = g["algun_pendiente"] or False
        else:
            g["todos_entregados"] = False
            g["algun_pendiente"] = True
    return [grupos[k] for k in orden]

@app.route("/admin")
def admin():
    if session.get("usuario") != ADMIN_USUARIO:
        return redirect(url_for("login"))
    usuarios = todos_usuarios()
    mensajes = leer_json(ARCHIVO_MENSAJES)
    carrito  = leer_json(ARCHIVO_CARRITO)
    compras  = [c for c in carrito if c.get("estado") in ("esperando_aprobacion", "aceptado")]
    compras.sort(key=lambda c: c.get("fecha", ""), reverse=True)
    todos_pedidos   = agrupar_compras(compras)
    pedidos_nuevos  = [p for p in todos_pedidos if p["estado"] == "esperando_aprobacion"]
    pedidos_aceptados = [p for p in todos_pedidos if p["estado"] == "aceptado"]
    notif_admin = sum(1 for m in mensajes if m.get("para") == ADMIN_USUARIO and not m.get("leido", False))
    return render_template("admin.html",
        usuarios=usuarios, mensajes=mensajes, compras=compras,
        pedidos_nuevos=pedidos_nuevos, pedidos_aceptados=pedidos_aceptados,
        notif_admin=notif_admin, tallas_validas=TALLAS_VALIDAS
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

@app.route("/api/admin/compra/entrega", methods=["POST"])
def api_admin_compra_entrega():
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False})
    data    = request.get_json()
    id_item = data.get("id")
    carrito = leer_json(ARCHIVO_CARRITO)
    for item in carrito:
        if item["id"] == id_item:
            item["entrega"] = "entregado" if item.get("entrega") == "pendiente" else "pendiente"
            break
    guardar_json(ARCHIVO_CARRITO, carrito)
    return jsonify({"success": True})

@app.route("/api/admin/compra/eliminar", methods=["POST"])
def api_admin_compra_eliminar():
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False})
    data    = request.get_json()
    id_item = data.get("id")
    carrito = leer_json(ARCHIVO_CARRITO)
    carrito = [c for c in carrito if c["id"] != id_item]
    guardar_json(ARCHIVO_CARRITO, carrito)
    return jsonify({"success": True})

@app.route("/api/admin/mensajes/hilo")
def api_admin_mensajes_hilo():
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify([])
    correo   = request.args.get("correo", "")
    mensajes = leer_json(ARCHIVO_MENSAJES)
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


def notificar_cliente_automatico(correo, texto):
    """Crea un mensaje automático de 'admin' hacia el cliente (ej: aviso de pedido modificado/aceptado)."""
    mensajes = leer_json(ARCHIVO_MENSAJES)
    mensajes.append({
        "id": len(mensajes) + 1, "de": ADMIN_USUARIO, "nombre": "Wampar Sport", "para": correo,
        "texto": texto, "imagen": None, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "leido": False
    })
    guardar_json(ARCHIVO_MENSAJES, mensajes)


@app.route("/api/admin/pedido/agregar_item", methods=["POST"])
def api_admin_pedido_agregar_item():
    """El admin agrega un producto nuevo a un pedido ya existente (esperando aprobación o aceptado)."""
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False})
    data = request.get_json() or {}
    pedido_id      = data.get("pedido_id")
    correo_cliente = data.get("correo_cliente")
    producto       = data.get("producto")
    precio         = data.get("precio", 0)
    carrito = leer_json(ARCHIVO_CARRITO)

    # Obtener el estado y nombre del cliente del pedido existente
    estado_pedido = "aceptado"
    nombre_cliente = correo_cliente
    for item in carrito:
        if item.get("pedido_id") == pedido_id:
            estado_pedido  = item.get("estado", "aceptado")
            nombre_cliente = item.get("nombre", correo_cliente)
            break

    if producto == "Banderola":
        metros = data.get("metros", 0)
        try:
            metros = float(metros)
        except (TypeError, ValueError):
            return jsonify({"success": False, "mensaje": "Metros no válido."})
        if metros <= 0 or metros > MAX_METROS_BANDEROLA:
            return jsonify({"success": False, "mensaje": f"Máximo {MAX_METROS_BANDEROLA} metros."})
        carrito.append({
            "id": siguiente_id_desde_lista(carrito),
            "correo": correo_cliente, "nombre": nombre_cliente,
            "producto": "Banderola", "precio": PRECIO_METRO_BANDEROLA, "cantidad": metros,
            "detalle": f"{metros:.2f} metros (1.50m alto x {metros:.2f}m ancho)",
            "pedido_id": pedido_id, "grupo_id": pedido_id,
            "estado": estado_pedido, "entrega": "pendiente", "adelanto": 0,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
    else:
        talla    = data.get("talla", "")
        cantidad = int(data.get("cantidad", 1))
        if talla not in TALLAS_VALIDAS:
            return jsonify({"success": False, "mensaje": "Talla no válida."})
        precio_real = PRECIOS_PRODUCTOS.get(producto, precio)
        carrito.append({
            "id": siguiente_id_desde_lista(carrito),
            "correo": correo_cliente, "nombre": nombre_cliente,
            "producto": producto, "precio": precio_real, "cantidad": cantidad,
            "talla": talla, "detalle": f"Talla {talla}",
            "pedido_id": pedido_id, "grupo_id": pedido_id,
            "estado": estado_pedido, "entrega": "pendiente", "adelanto": 0,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

    guardar_json(ARCHIVO_CARRITO, carrito)
    notificar_cliente_automatico(correo_cliente, f"🔄 Tu pedido fue modificado por la tienda (se agregó un producto). Revisa tu pedido en 'Mis Compras' — si ves algo que no corresponde, avísanos por este chat.")
    return jsonify({"success": True})


@app.route("/api/admin/pedido/aceptar", methods=["POST"])
def api_admin_pedido_aceptar():
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False})
    pedido_id = (request.get_json() or {}).get("pedido_id")
    carrito = leer_json(ARCHIVO_CARRITO)
    correo_cliente = None
    for item in carrito:
        if item.get("pedido_id") == pedido_id and item.get("estado") == "esperando_aprobacion":
            item["estado"] = "aceptado"
            correo_cliente = item.get("correo")
    guardar_json(ARCHIVO_CARRITO, carrito)
    if correo_cliente:
        notificar_cliente_automatico(correo_cliente, "✅ Tu pedido ya fue aceptado por la tienda. Ya no podrás modificarlo desde tu cuenta — si necesitas un cambio, escríbenos por este chat.")
    return jsonify({"success": True})


@app.route("/api/admin/pedido/rechazar", methods=["POST"])
def api_admin_pedido_rechazar():
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False})
    pedido_id = (request.get_json() or {}).get("pedido_id")
    carrito = leer_json(ARCHIVO_CARRITO)
    correo_cliente = None
    for item in carrito:
        if item.get("pedido_id") == pedido_id and item.get("estado") == "esperando_aprobacion":
            item["estado"] = "rechazado"
            correo_cliente = item.get("correo")
    guardar_json(ARCHIVO_CARRITO, carrito)
    if correo_cliente:
        notificar_cliente_automatico(correo_cliente, "❌ Tu pedido no pudo ser aceptado por la tienda. Escríbenos por este chat si quieres más información o hacer un nuevo pedido.")
    return jsonify({"success": True})


@app.route("/api/admin/pedido/editar_item", methods=["POST"])
def api_admin_pedido_editar_item():
    """El admin edita cantidad, talla o metros (banderola) de UNA línea de un pedido."""
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False})
    data = request.get_json() or {}
    item_id  = data.get("id")
    cantidad = data.get("cantidad")
    talla    = data.get("talla")
    metros   = data.get("metros")
    carrito = leer_json(ARCHIVO_CARRITO)
    correo_cliente = None
    for item in carrito:
        if item.get("id") == item_id:
            if item.get("producto") == "Banderola" and metros is not None:
                try:
                    metros = float(metros)
                    if 0 < metros <= MAX_METROS_BANDEROLA:
                        item["cantidad"] = metros
                        item["detalle"] = f"{metros:.2f} metros (1.50m alto x {metros:.2f}m ancho)"
                except (TypeError, ValueError):
                    pass
            elif cantidad is not None:
                try:
                    cantidad = float(cantidad)
                    if cantidad > 0:
                        item["cantidad"] = cantidad
                except (TypeError, ValueError):
                    pass
            if talla and item.get("producto") != "Banderola":
                item["talla"] = talla
                item["detalle"] = f"Talla {talla}"
            correo_cliente = item.get("correo")
            break
    guardar_json(ARCHIVO_CARRITO, carrito)
    if correo_cliente:
        notificar_cliente_automatico(correo_cliente, "🔄 Tu pedido fue modificado por la tienda (cambio de cantidad o talla). Revisa tu pedido en 'Mis Compras' — si ves algo que no corresponde, avísanos por este chat.")
    return jsonify({"success": True})


@app.route("/api/admin/pedido/eliminar_item", methods=["POST"])
def api_admin_pedido_eliminar_item():
    """El admin elimina UNA línea de un pedido (ya aceptado o esperando aprobación), notificando al cliente."""
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False})
    item_id = (request.get_json() or {}).get("id")
    carrito = leer_json(ARCHIVO_CARRITO)
    correo_cliente = None
    nuevo_carrito = []
    for item in carrito:
        if item.get("id") == item_id:
            correo_cliente = item.get("correo")
            continue
        nuevo_carrito.append(item)
    guardar_json(ARCHIVO_CARRITO, nuevo_carrito)
    if correo_cliente:
        notificar_cliente_automatico(correo_cliente, "🔄 Tu pedido fue modificado por la tienda (se quitó un producto). Revisa tu pedido en 'Mis Compras' — si ves algo que no corresponde, avísanos por este chat.")
    return jsonify({"success": True})


@app.route("/api/admin/pedido/adelanto", methods=["POST"])
def api_admin_pedido_adelanto():
    """El admin registra/actualiza el monto de adelanto pagado para un pedido completo (todas sus líneas)."""
    if session.get("usuario") != ADMIN_USUARIO:
        return jsonify({"success": False})
    data = request.get_json() or {}
    pedido_id = data.get("pedido_id")
    monto = data.get("adelanto")
    try:
        monto = float(monto)
    except (TypeError, ValueError):
        return jsonify({"success": False, "mensaje": "El monto ingresado no es un número válido."})
    if monto < 0:
        return jsonify({"success": False, "mensaje": "El monto del adelanto no puede ser negativo."})
    if monto > MAX_MONTO_ADELANTO:
        return jsonify({"success": False, "mensaje": f"El monto ingresado parece demasiado alto (máximo S/ {MAX_MONTO_ADELANTO})."})
    carrito = leer_json(ARCHIVO_CARRITO)
    encontrado = False
    for item in carrito:
        if item.get("pedido_id") == pedido_id:
            item["adelanto"] = monto
            encontrado = True
    guardar_json(ARCHIVO_CARRITO, carrito)
    return jsonify({"success": encontrado})


if __name__ == "__main__":
    app.run(debug=True)