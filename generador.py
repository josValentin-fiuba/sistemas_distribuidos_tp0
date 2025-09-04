import sys

TAB = "  "

def generar_compose_file(filename, cant_clientes):
    with open(filename, "w") as f:
        def wln(cant_tabs, text):
            f.write(f"{cant_tabs * TAB}{text}\n")

        wln(0, "name: tp0")
        wln(0, "services:")
        wln(1, "server:")
        wln(2, "container_name: server")
        wln(2, "image: server:latest")
        wln(2, "entrypoint: python3 /main.py")
        wln(2, "environment:")
        wln(3, "- PYTHONUNBUFFERED=1")
        wln(2, "networks:")
        wln(3, "- testing_net")
        wln(2, "volumes:")
        wln(3, "- ./server/config.ini:/config.ini:ro\n")

        for i in range(1, cant_clientes + 1):
            wln(1, f"client{i}:")
            wln(2, f"container_name: client{i}")
            wln(2, f"image: client:latest")
            wln(2, f"entrypoint: /client")
            wln(2, f"environment:")
            wln(3, f"- CLI_ID={i}")
            wln(3, f"- NOMBRE=nombre_{i}")
            wln(3, f"- APELLIDO=apellido_{i}")
            wln(3, f"- DOCUMENTO={i}")
            wln(3, f"- NACIMIENTO=2000-09-0{i}")
            wln(3, f"- NUMERO={i}")
            wln(2, f"networks:")
            wln(3, f"- testing_net")
            wln(2, f"depends_on:")
            wln(3, f"- server")
            wln(2, f"volumes:")
            wln(3, f"- ./client/config.yaml:/config.yaml:ro")
            wln(3, f"- ./client/params.yaml:/params.yaml:ro")
            wln(3, f"- ./.data/agency-{i}.csv:/.data/agency-{i}.csv:ro\n")

        wln(0, "networks:")
        wln(1, "testing_net:")
        wln(2, "ipam:")
        wln(3, "driver: default")
        wln(3, "config:")
        wln(4, "- subnet: 172.25.125.0/24")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Argumentos incorrectos")
        sys.exit(1)

    file = sys.argv[1]
    cant_clientes = int(sys.argv[2])
    generar_compose_file(file, cant_clientes)