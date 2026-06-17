const formContacto = document.getElementById("formContacto");
const respuestaFormulario = document.getElementById("respuestaFormulario");

formContacto.addEventListener("submit", function(evento) {
    evento.preventDefault();

    const nombre  = document.getElementById("nombre").value.trim();
    const correo  = document.getElementById("correo").value.trim();
    const mensaje = document.getElementById("mensaje").value.trim();

    if (nombre === "" || correo === "" || mensaje === "") {
        respuestaFormulario.textContent = "Por favor, completa todos los campos.";
        respuestaFormulario.style.color = "red";
        return;
    }

    fetch("/api/contacto", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            nombre:  nombre,
            correo:  correo,
            mensaje: mensaje
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            respuestaFormulario.textContent = "¡Mensaje enviado correctamente!";
            respuestaFormulario.style.color = "#06b6d4";
            formContacto.reset();
        }
    })
    .catch(error => {
        respuestaFormulario.textContent = "Ocurrió un error al enviar el mensaje.";
        respuestaFormulario.style.color = "red";
    });
});
