import socket
import threading
import time
import struct  # Necessário para converter IP para o campo float
import proto.robot_comm_pb2 as proto



class RobotInterface:
    def __init__(self, UDP_IP = "255.255.255.255", UDP_PORT = 5000, TCP_IP = "0.0.0.0", TCP_PORT = 5001):
        self.running = True
        self.UDP_IP = UDP_IP
        self.UDP_PORT = UDP_PORT
        self.TCP_IP = TCP_IP
        self.TCP_PORT = TCP_PORT
        # Setup UDP (Sender)
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Iniciar Thread de Telemetria (TCP Server)
        self.tcp_thread = threading.Thread(target=self._tcp_server_task)
        self.tcp_thread.daemon = True
        self.tcp_thread.start()

    def send_motion_command(self, robot_id, vx, vy, vw, kick_h=0, kick_v=0):
        """Envia comando de movimentação para um robô específico via UDP"""
        packet = proto.RobotPacket()
        packet.robot_id = robot_id

        packet.motion.vel_x = vx
        packet.motion.vel_y = vy
        packet.motion.vel_w = vw
        packet.motion.kick_h = kick_h
        packet.motion.kick_v = kick_v

        msg = packet.SerializeToString()
        self.udp_sock.sendto(msg, (self.UDP_IP, self.UDP_PORT))
        print(f"[UDP] Comando de Movimento enviado para Robô {robot_id}")

    def send_info_request(self, robot_id, info_index):
        """Solicita informações (IP, MAC, etc) via UDP"""
        packet = proto.RobotPacket()
        packet.robot_id = robot_id
        packet.request.info_index = info_index

        msg = packet.SerializeToString()
        self.udp_sock.sendto(msg, (self.UDP_IP, self.UDP_PORT))
        print(f"[UDP] Request (index {info_index}) enviado para Robô {robot_id}")

    def send_config_command(self, robot_id, param_id, value):
        """
        Envia configurações para o robô.
        Se 'value' for string, preenche text_value. Se for número, preenche value.
        """
        packet = proto.RobotPacket()
        packet.robot_id = robot_id
        packet.config.param_id = param_id

        if isinstance(value, str):
            packet.config.text_value = value
        else:
            packet.config.value = float(value)

        msg = packet.SerializeToString()
        self.udp_sock.sendto(msg, (self.UDP_IP, self.UDP_PORT))
        print(f"[UDP] Config {param_id} enviada: {value}")

    def _tcp_server_task(self):
        """Servidor TCP que recebe telemetria e respostas dos robôs"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.TCP_IP, self.TCP_PORT))
        server.listen(5)
        print(f"[TCP] Servidor ativo na porta {self.TCP_PORT}...")

        while self.running:
            client, addr = server.accept()
            threading.Thread(target=self._handle_robot_client, args=(client, addr)).start()

    def _handle_robot_client(self, client_socket, addr):
        print(f"[TCP] Conexão estabelecida com {addr}")
        with client_socket:
            while self.running:
                try:
                    # 1. Lê os primeiros 4 bytes para saber o tamanho da mensagem (Little Endian)
                    raw_msg_len = client_socket.recv(4)
                    if not raw_msg_len: break

                    msg_len = struct.unpack('<I', raw_msg_len)[0]

                    # 2. Lê exatamente a quantidade de bytes informada
                    data = b''
                    while len(data) < msg_len:
                        chunk = client_socket.recv(msg_len - len(data))
                        if not chunk: break
                        data += chunk

                    packet = proto.RobotPacket()
                    packet.ParseFromString(data)
                    payload_type = packet.WhichOneof("payload")

                    if payload_type == 'telemetry':
                        pass  # Processar telemetria
                    elif payload_type == 'response':
                        r = packet.response
                        print(f"[RESPOSTA] Índice {r.info_index}: {r.text_value or r.value}")

                except Exception as e:
                    print(f"[ERRO TCP] Falha ao processar dados de {addr}: {e}")
                    break

    def broadcast_network_config(self):
        self.send_config_command(0xFF, 1, "192.168.168.102")



# --- Exemplo de Uso ---
if __name__ == "__main__":
    robot = RobotInterface()

    try:
        time.sleep(1)
        robot.send_config_command(robot_id=0, param_id=1, value="192.168.168.102")

        time.sleep(0.5)
        robot.send_config_command(robot_id=0, param_id=2, value=5001)
        robot.send_config_command(robot_id=2, param_id=0, value=16)

        while True:
            robot.send_motion_command(robot_id=15, vx=0.2, vy=0.0, vw=0.0)
            time.sleep(2)
            robot.send_info_request(robot_id=15, info_index=1)
            time.sleep(2)


    except KeyboardInterrupt:
        robot.running = False