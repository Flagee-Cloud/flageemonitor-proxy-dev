# ssh_manager.py

import paramiko
import socket
import os
import logging
import time

class SSHSession:
    def __init__(self, host: str, port: int, user: str, password: str, timeout: int = 30):
        self.host     = host
        self.port     = port
        self.user     = user
        self.password = password
        self.timeout  = timeout
        self._client  = None
        self._connect()

    def _connect(self):
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            timeout=self.timeout,
            look_for_keys=False,
            allow_agent=False
        )

    def run(
        self,
        cmd: str,
        use_sudo: bool   = False,
        timeout: int     = None,
        get_pty: bool    = True,
        logger: logging.Logger = None,
        fire_and_forget: bool = False
    ) -> tuple[int, str, str]:
        """
        Executa um comando remoto, logando a saída STDOUT/STDERR se o logger estiver em modo DEBUG.
        """
        final_cmd = cmd
        should_get_pty = get_pty

        if use_sudo:
            final_cmd = f"sudo -S -p '' {cmd}"
            should_get_pty = False

        effective_timeout = timeout or self.timeout
        
        stdin, stdout, stderr = self._client.exec_command(
            final_cmd,
            timeout=effective_timeout,
            get_pty=should_get_pty
        )

        if use_sudo:
            stdin.write(self.password + "\n")
            stdin.flush()

        if fire_and_forget:
            if logger:
                logger.info(f"Comando '{cmd}' enviado em modo 'fire-and-forget'. Aguardando 1s para garantir a entrega.")
            time.sleep(1)
            stdout.channel.close()
            return 0, "", ""
            
        try:
            channel = stdout.channel
            channel.settimeout(effective_timeout)
            exit_status = channel.recv_exit_status()
            out = stdout.read().decode(errors='ignore')
            err = stderr.read().decode(errors='ignore')
        except socket.timeout:
            exit_status = -1
            out = ""
            err = f"Timeout de {effective_timeout}s excedido ao aguardar a saida do comando."
            stdout.channel.close()

        # --- INÍCIO DA MELHORIA DE LOG ---
        if logger:
            # Verifica se o logger está configurado para o nível DEBUG
            is_debug_mode = logger.isEnabledFor(logging.DEBUG)

            if exit_status == 0:
                logger.info(f"'{cmd}' -> SUCESSO (exit {exit_status})")
                # Se estiver em modo debug e houver alguma saída, exibe-a.
                if is_debug_mode and out.strip():
                    logger.debug(f"STDOUT:\n---\n{out.strip()}\n---")
            else:
                logger.error(f"'{cmd}' -> FALHA (exit {exit_status})")
                # Em caso de falha, sempre exibe a saída para facilitar a depuração.
                if out.strip():
                    logger.error(f"STDOUT:\n---\n{out.strip()}\n---")
                if err.strip():
                    logger.error(f"STDERR:\n---\n{err.strip()}\n---")
        # --- FIM DA MELHORIA DE LOG ---

        return exit_status, out, err

    def put(self, local_path: str, remote_path: str, use_sudo: bool = False):
        sftp = None
        try:
            sftp = self._client.open_sftp()
            sftp.get_channel().settimeout(self.timeout)

            if not use_sudo:
                sftp.put(local_path, remote_path)
            else:
                tmp = f"/tmp/{os.path.basename(remote_path)}"
                sftp.put(local_path, tmp)
                self.run(f"mv {tmp} {remote_path}", use_sudo=True)
        
        except socket.timeout:
            raise TimeoutError(f"Timeout de {self.timeout}s excedido durante a transferencia do arquivo para {self.host}")
        
        finally:
            if sftp:
                sftp.close()

    def close(self):
        if self._client:
            self._client.close()
            self._client = None