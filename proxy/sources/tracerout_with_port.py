from scapy.all import IP, UDP, TCP, ICMP, sr1
from time import time
import socket

def resolve_fqdn(ip):
    """
    Tenta resolver o FQDN (nome de domínio completo) de um endereço IP.
    Retorna o nome ou o próprio IP se a resolução falhar.
    """
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return ip

def traceroute_with_port(destination_ip, destination_port, protocol="UDP", max_hops=30, timeout=2):
    """
    Realiza um traceroute customizado para um destino específico (IP, porta e protocolo).
    """
    print(f"Traceroute para {destination_ip}:{destination_port} usando {protocol.upper()} com até {max_hops} saltos\n")
    print(f"{'Salto':<6} {'IP/FQDN':<40} {'Latência (ms)':<15} {'Status'}")
    print("-" * 80)

    for ttl in range(1, max_hops + 1):
        # Configura o pacote IP com TTL e protocolo
        if protocol.upper() == "UDP":
            pkt = IP(dst=destination_ip, ttl=ttl) / UDP(dport=destination_port)
        elif protocol.upper() == "TCP":
            pkt = IP(dst=destination_ip, ttl=ttl) / TCP(dport=destination_port, flags="S")

        # Marca o início do tempo
        start_time = time()

        # Envia o pacote e aguarda a resposta
        reply = sr1(pkt, verbose=0, timeout=timeout)

        # Calcula a latência
        latency = round((time() - start_time) * 1000, 2)

        if reply is None:
            print(f"{ttl:<6} {'*':<40} {'-':<15} {'Sem resposta'}")
        elif reply.haslayer(ICMP):
            if reply.getlayer(ICMP).type == 3:  # Destination Unreachable
                fqdn = resolve_fqdn(reply.src)
                print(f"{ttl:<6} {fqdn:<40} {latency:<15} {'Destino inalcançável'}")
            else:
                fqdn = resolve_fqdn(reply.src)
                print(f"{ttl:<6} {fqdn:<40} {latency:<15} {'Resposta ICMP'}")
        elif reply.haslayer(TCP) and reply.getlayer(TCP).flags == 0x12:  # SYN-ACK
            fqdn = resolve_fqdn(reply.src)
            print(f"{ttl:<6} {fqdn:<40} {latency:<15} {'Resposta TCP'}")
            # Envia um RST para fechar a conexão
            sr1(IP(dst=destination_ip) / TCP(dport=destination_port, flags="R"), timeout=timeout, verbose=0)
            print("\nDestino alcançado!")
            return
        else:
            fqdn = resolve_fqdn(reply.src)
            print(f"{ttl:<6} {fqdn:<40} {latency:<15} {'Resposta'}")

    print("\nLimite de saltos atingido. Destino não alcançado.")

if __name__ == "__main__":
    destination_ip = input("Digite o IP ou domínio de destino: ")
    destination_port = int(input("Digite a porta de destino: "))
    protocol = input("Digite o protocolo (UDP/TCP): ").strip().upper()

    traceroute_with_port(destination_ip, destination_port, protocol=protocol)
