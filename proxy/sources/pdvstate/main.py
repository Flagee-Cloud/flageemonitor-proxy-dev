import redis
import time
import json
import logging # Import the logging library
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

# --- NEW: Configure Logging ---
# Sets up a logger that will print messages to the console (which journalctl captures)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Modelos de Dados (Pydantic) ---
class PdvEvent(BaseModel):
    loja_id: int
    pdv_id: int
    event_type: str
    data: Dict[str, Any] = {}

# --- Conexão com Redis ---
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        redis_client.ping()
        logging.info("Conexão com o Redis estabelecida com sucesso!")
    except redis.exceptions.ConnectionError as e:
        logging.error(f"ERRO CRÍTICO: Não foi possível conectar ao Redis. {e}")
        redis_client = None
    yield
    if redis_client:
        logging.info("Encerrando a conexão com o Redis.")
        redis_client.close()

# --- Configuração da Aplicação ---
app = FastAPI(
    title="PDVState API",
    description="API avançada para monitoramento em tempo real dos PDVs e transações.",
    version="2.3.0", # Version incremented with better logging
    lifespan=lifespan
)

# --- Variável global para cache das regras ---
rules_cache = {}

# --- Função para carregar as regras do arquivo ---
def load_rules():
    global rules_cache
    try:
        with open("rules.json", "r") as f:
            rules_cache = json.load(f)
            logging.info("Arquivo de regras (rules.json) carregado com sucesso.")
            return rules_cache
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"ERRO CRÍTICO: Não foi possível carregar o arquivo 'rules.json'. {e}")
        rules_cache = {"version": "0.0.0", "rules": {}}
        return rules_cache

load_rules()

# --- Endpoints de Configuração ---

@app.get("/config/version", response_class=Response)
async def get_config_version():
    loaded_rules = load_rules()
    version = loaded_rules.get("version", "0.0.0")
    return Response(content=version, media_type="text/plain")

@app.get("/config/rules")
async def get_config_rules():
    return rules_cache if rules_cache else load_rules()


# --- Endpoint de Eventos ---
@app.post("/pdv/event")
async def process_pdv_event(event: PdvEvent):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Serviço indisponível: Sem conexão com o Redis.")
    
    pdv_key = f"pdv:{event.loja_id}:{event.pdv_id}"
    
    # Roteador de eventos
    if event.event_type == "UPDATE_OPERADOR":
        operador_id = event.data.get("operador_id", "desconhecido")
        logging.info(f"PDV {event.loja_id}-{event.pdv_id}: Operador {operador_id} logado.")
        estado_atual = redis_client.hget(pdv_key, "estado_atual")
        pipe = redis_client.pipeline()
        pipe.hset(pdv_key, "operador_id", operador_id)
        if estado_atual == "FECHADO" or estado_atual is None:
             pipe.hset(pdv_key, "estado_atual", "LIVRE")
        pipe.execute()
        return {"message": "Operador logado."}

    elif event.event_type == "OPERADOR_LOGOFF":
        logging.info(f"PDV {event.loja_id}-{event.pdv_id}: Operador deslogou.")
        redis_client.hset(pdv_key, mapping={"estado_atual": "FECHADO", "operador_id": ""})
        return {"message": "Operador deslogou."}

    elif event.event_type == "INICIO_VENDA":
        logging.info(f"PDV {event.loja_id}-{event.pdv_id}: Venda iniciada.")
        redis_client.hset(pdv_key, "estado_atual", "VENDENDO")
        return {"message": "PDV em estado de venda."}

    elif event.event_type == "VENDA_CUPOM":
        cupom = event.data.get("cupom_fiscal")
        logging.info(f"PDV {event.loja_id}-{event.pdv_id}: Venda criada com Cupom Fiscal {cupom}.")
        if not cupom: raise HTTPException(status_code=400, detail="Cupom fiscal não informado.")
        venda_key = f"venda:{cupom}"
        redis_client.hset(pdv_key, "venda_atual_cupom", cupom)
        venda_data = {
            "cupom_fiscal": cupom, "loja_id": event.loja_id, "pdv_id": event.pdv_id,
            "operador_id": redis_client.hget(pdv_key, "operador_id"),
            "timestamp_inicio": int(time.time()), "status": "EM_ANDAMENTO"
        }
        redis_client.set(venda_key, json.dumps(venda_data))
        return {"message": f"Venda {cupom} iniciada."}

    elif event.event_type == "VENDA_DETALHES":
        cupom = redis_client.hget(pdv_key, "venda_atual_cupom")
        valor = event.data.get('valor_total')
        itens = event.data.get('qtd_itens')
        logging.info(f"PDV {event.loja_id}-{event.pdv_id}: Detalhes da Venda {cupom} recebidos. Valor: R$ {valor}, Itens: {itens}.")
        if not cupom: return {"message": "Detalhes recebidos sem venda em andamento."}
        venda_key = f"venda:{cupom}"
        venda_str = redis_client.get(venda_key)
        if venda_str:
            venda_data = json.loads(venda_str)
            venda_data["valor_total"] = valor
            venda_data["qtd_itens"] = itens
            redis_client.set(venda_key, json.dumps(venda_data))
        return {"message": f"Detalhes da venda {cupom} atualizados."}

    elif event.event_type == "PAGAMENTO":
        cupom = event.data.get("cupom_fiscal")
        forma_pagamento = event.data.get('forma_pagamento')
        logging.info(f"PDV {event.loja_id}-{event.pdv_id}: Pagamento para Venda {cupom} recebido. Forma: {forma_pagamento}.")
        if not cupom: return {"message": "Pagamento recebido sem cupom."}
        venda_key = f"venda:{cupom}"
        venda_str = redis_client.get(venda_key)
        if venda_str:
            venda_data = json.loads(venda_str)
            venda_data["forma_pagamento"] = forma_pagamento
            redis_client.set(venda_key, json.dumps(venda_data))
        return {"message": f"Pagamento da venda {cupom} atualizado."}

    # NOVO: Associa o cupom do TEF à venda em andamento
    elif event.event_type == "PAGAMENTO_CUPOM":
        cupom = event.data.get("cupom_fiscal")
        if not cupom: return {"message": "Cupom de pagamento sem ID."}

        # Apenas atualiza o cupom na venda que já deve existir
        venda_key = f"venda:{cupom}"
        logging.info(f"PDV {event.loja_id}-{event.pdv_id}: Associando TEF à Venda {cupom}.")
        # Se necessário, você pode adicionar o cupom do TEF à venda aqui.
        return {"message": f"Cupom TEF {cupom} associado."}

    # NOVO: Atualiza a forma de pagamento na venda em andamento
    elif event.event_type == "PAGAMENTO_FORMA":
        forma_pagamento = event.data.get("forma_pagamento", "desconhecida").strip()
        # Pega a venda que está em andamento neste PDV
        cupom = redis_client.hget(pdv_key, "venda_atual_cupom")
        if not cupom: return {"message": "Forma de pagamento recebida, mas nenhuma venda em andamento."}
        
        logging.info(f"PDV {event.loja_id}-{event.pdv_id}: Pagamento para Venda {cupom}. Forma: {forma_pagamento}.")
        venda_key = f"venda:{cupom}"
        venda_str = redis_client.get(venda_key)
        if venda_str:
            venda_data = json.loads(venda_str)
            venda_data["forma_pagamento"] = forma_pagamento
            redis_client.set(venda_key, json.dumps(venda_data))
        return {"message": f"Pagamento da venda {cupom} atualizado."}

    elif event.event_type == "ERRO_TEF":
        rc = event.data.get('rc')
        msg = event.data.get('msg')
        logging.warning(f"PDV {event.loja_id}-{event.pdv_id}: ERRO DE PAGAMENTO! Código: {rc}, Mensagem: '{msg}'.")
        cupom = redis_client.hget(pdv_key, "venda_atual_cupom")
        if cupom:
            venda_key = f"venda:{cupom}"
            venda_str = redis_client.get(venda_key)
            if venda_str:
                venda_data = json.loads(venda_str)
                venda_data["status"] = "FALHA_PAGAMENTO"
                venda_data["erro_tef"] = event.data
                redis_client.set(venda_key, json.dumps(venda_data))
        return {"message": "Erro TEF registrado."}

    elif event.event_type == "FIM_VENDA":
        logging.info(f"PDV {event.loja_id}-{event.pdv_id}: Fim da operação de venda.")
        cupom = redis_client.hget(pdv_key, "venda_atual_cupom")
        if cupom:
            venda_key = f"venda:{cupom}"
            venda_str = redis_client.get(venda_key)
            if venda_str:
                venda_data = json.loads(venda_str)
                if venda_data.get("status") == "EM_ANDAMENTO":
                    venda_data["status"] = "CONCLUIDA"
                venda_data["timestamp_fim"] = int(time.time())
                duracao = venda_data["timestamp_fim"] - venda_data.get("timestamp_inicio", venda_data["timestamp_fim"])
                venda_data["duracao_segundos"] = duracao
                redis_client.set(venda_key, json.dumps(venda_data))
                if venda_data["status"] == "CONCLUIDA":
                    pipe = redis_client.pipeline()
                    pipe.hincrby(pdv_key, "contador_vendas_dia", 1)
                    pipe.hincrbyfloat(pdv_key, "duracao_total_vendas_dia", duracao)
                    pipe.execute()
        redis_client.hset(pdv_key, mapping={"estado_atual": "LIVRE", "venda_atual_cupom": ""})
        return {"message": "Venda finalizada."}
        
    logging.warning(f"PDV {event.loja_id}-{event.pdv_id}: Recebido evento desconhecido: '{event.event_type}'.")
    return {"message": "Tipo de evento desconhecido."}

# --- Endpoints de Consulta ---
# (Os endpoints de consulta não precisam de alteração)

@app.get("/pdv/{loja_id}/{pdv_id}/status")
async def get_pdv_status(loja_id: int, pdv_id: int):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Serviço indisponível.")
    redis_key = f"pdv:{loja_id}:{pdv_id}"
    data = redis_client.hgetall(redis_key)
    if not data:
        raise HTTPException(status_code=404, detail="PDV não encontrado")
    return {
        "loja_id": loja_id, "pdv_id": pdv_id,
        "estado": data.get("estado_atual", "DESCONHECIDO"),
        "ultima_mudanca_em": int(data.get("timestamp_inicio_venda", 0))
    }

@app.get("/pdv/{loja_id}/{pdv_id}/stats")
async def get_pdv_stats(loja_id: int, pdv_id: int):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Serviço indisponível.")
    redis_key = f"pdv:{loja_id}:{pdv_id}"
    data = redis_client.hgetall(redis_key)
    if not data:
        raise HTTPException(status_code=404, detail="PDV não encontrado")
    total_vendas = int(data.get("contador_vendas_dia", 0))
    duracao_total = float(data.get("duracao_total_vendas_dia", 0.0))
    tempo_medio = round(duracao_total / total_vendas, 2) if total_vendas > 0 else 0
    return {
        "loja_id": loja_id, "pdv_id": pdv_id,
        "total_vendas": total_vendas,
        "tempo_medio_venda_segundos": tempo_medio
    }

@app.get("/venda/{cupom_fiscal}")
async def get_venda_details(cupom_fiscal: str):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Serviço indisponível.")
    venda_key = f"venda:{cupom_fiscal}"
    venda_str = redis_client.get(venda_key)
    if not venda_str:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")
    return json.loads(venda_str)